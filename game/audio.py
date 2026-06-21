"""game/audio.py — procedural audio engine (music + SFX synthesis) for Sangeroasa."""
import io
import os
import math
import time
import wave
import random
from array import array
from typing import Optional, List, Dict, Tuple, Any, Union

import pygame


class GameAudio:
    def __init__(self) -> None:
        self.enabled = False
        self.sample_rate = 12000
        self.sfx: Dict[str, pygame.mixer.Sound] = {}
        self.sfx_variants: Dict[str, List[pygame.mixer.Sound]] = {}
        self.music: Dict[str, pygame.mixer.Sound] = {}
        self.ambience: Dict[str, pygame.mixer.Sound] = {}
        self.current_music = ""
        self.current_ambience = ""
        self.last_sfx_tick: Dict[str, int] = {}
        self.music_channel: Optional[pygame.mixer.Channel] = None
        self.ui_channel: Optional[pygame.mixer.Channel] = None
        self.ambience_channel: Optional[pygame.mixer.Channel] = None
        self.footstep_timer = 0.0
        self.sound_root = os.path.join("assets", "sounds")
        self.theme_music_root = os.path.join("assets", "sound")
        self.using_external_audio_pack = False

    @staticmethod
    def _midi_to_freq(note: int) -> float:
        return 440.0 * (2.0 ** ((float(note) - 69.0) / 12.0))

    def _sound_from_mono(self, samples: array, sample_rate: Optional[int] = None) -> Optional[pygame.mixer.Sound]:
        if not self.enabled:
            return None
        sr = int(sample_rate or self.sample_rate)
        if sr <= 1000 or len(samples) <= 4:
            return None
        bio = io.BytesIO()
        try:
            with wave.open(bio, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sr)
                wav_file.writeframes(samples.tobytes())
            bio.seek(0)
            return pygame.mixer.Sound(file=bio)
        except (pygame.error, wave.Error):
            return None

    def _sound_from_stereo(
        self,
        left_samples: List[float],
        right_samples: List[float],
        sample_rate: Optional[int] = None,
    ) -> Optional[pygame.mixer.Sound]:
        if not self.enabled:
            return None
        if len(left_samples) != len(right_samples) or len(left_samples) <= 4:
            return None
        sr = int(sample_rate or self.sample_rate)
        if sr <= 1000:
            return None
        peak = 0.0001
        for idx in range(len(left_samples)):
            lv = abs(float(left_samples[idx]))
            rv = abs(float(right_samples[idx]))
            if lv > peak:
                peak = lv
            if rv > peak:
                peak = rv
        gain = 1.0 if peak <= 1.0 else (1.0 / peak)
        interleaved = array("h")
        for idx in range(len(left_samples)):
            left_val = int(max(-1.0, min(1.0, float(left_samples[idx]) * gain)) * 32767.0)
            right_val = int(max(-1.0, min(1.0, float(right_samples[idx]) * gain)) * 32767.0)
            interleaved.append(left_val)
            interleaved.append(right_val)
        bio = io.BytesIO()
        try:
            with wave.open(bio, "wb") as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sr)
                wav_file.writeframes(interleaved.tobytes())
            bio.seek(0)
            return pygame.mixer.Sound(file=bio)
        except (pygame.error, wave.Error):
            return None

    @staticmethod
    def _wave_value(phase: float, wave_kind: str) -> float:
        frac = phase - math.floor(phase)
        sine = math.sin(math.tau * frac)
        if wave_kind == "square":
            return 1.0 if sine >= 0.0 else -1.0
        if wave_kind == "triangle":
            return (2.0 / math.pi) * math.asin(sine)
        if wave_kind == "saw":
            return 2.0 * frac - 1.0
        return sine

    def _synth_effect(
        self,
        duration: float,
        base_freq: float,
        wave_kind: str = "sine",
        sweep: float = 0.0,
        volume: float = 0.45,
        noise: float = 0.0,
        vibrato_hz: float = 0.0,
        vibrato_depth: float = 0.0,
        punch: float = 0.0,
        seed: int = 0,
    ) -> Optional[pygame.mixer.Sound]:
        if not self.enabled:
            return None
        sr = self.sample_rate
        total = max(8, int(duration * sr))
        attack = max(0.004, duration * 0.12)
        release = max(0.02, duration * 0.30)
        decay = max(0.02, duration * 0.18)
        sustain_start = min(duration, attack + decay)
        rng = random.Random(seed)
        phase_left = rng.random()
        phase_right = rng.random()
        phase_sub = rng.random()
        left: List[float] = [0.0] * total
        right: List[float] = [0.0] * total
        detune_amt = 0.002 + max(0.0, abs(vibrato_depth)) * 0.014
        pan_hz = 0.35 + (abs(base_freq) % 130.0) / 520.0
        for i in range(total):
            t = i / sr
            progress = i / max(1, total - 1)
            freq = max(14.0, base_freq * (1.0 + sweep * progress))
            if vibrato_hz > 0.0 and vibrato_depth > 0.0:
                vib = math.sin(math.tau * vibrato_hz * t) * vibrato_depth
                freq *= (1.0 + vib)
            phase_left = (phase_left + (freq * (1.0 - detune_amt)) / sr) % 1.0
            phase_right = (phase_right + (freq * (1.0 + detune_amt)) / sr) % 1.0
            phase_sub = (phase_sub + max(14.0, freq * 0.5) / sr) % 1.0

            core_left = self._wave_value(phase_left, wave_kind)
            core_right = self._wave_value(phase_right, wave_kind)
            harm_left = math.sin(math.tau * ((phase_left * 2.03) % 1.0))
            harm_right = math.sin(math.tau * ((phase_right * 1.97) % 1.0))
            sub = math.sin(math.tau * phase_sub)
            hiss_left = (rng.random() * 2.0 - 1.0) * noise
            hiss_right = (rng.random() * 2.0 - 1.0) * noise

            if t < attack:
                env = t / attack
            elif t < sustain_start:
                dec_t = (t - attack) / max(0.001, decay)
                env = 1.0 - dec_t * 0.32
            elif t > duration - release:
                env = max(0.0, (duration - t) / release) * 0.68
            else:
                env = 0.68
            if punch > 0.0:
                env *= (1.0 + punch * (1.0 - progress))
            pan = math.sin(math.tau * pan_hz * t + (seed % 11) * 0.21)
            pan_left = 1.0 - 0.18 * pan
            pan_right = 1.0 + 0.18 * pan

            left[i] = (core_left * 0.60 + harm_left * 0.24 + sub * 0.18 + hiss_left) * env * volume * pan_left
            right[i] = (core_right * 0.60 + harm_right * 0.24 + sub * 0.18 + hiss_right) * env * volume * pan_right

        # Add a short crossfeed echo to avoid dry/flat mono-like output.
        delay_a = max(1, int(sr * (0.021 + 0.006 * min(1.0, abs(sweep)))))
        delay_b = max(delay_a + 1, int(sr * (0.039 + 0.008 * min(1.0, abs(vibrato_depth) * 2.0))))
        feedback = 0.15 + min(0.12, 0.06 * abs(sweep) + 0.28 * noise)
        cross = 0.08 + min(0.10, 0.10 * abs(vibrato_depth) + 0.02 * punch)
        for i in range(delay_b, total):
            left[i] += left[i - delay_a] * feedback + right[i - delay_b] * cross
            right[i] += right[i - delay_a] * feedback + left[i - delay_b] * cross

        # Gentle low-pass smoothing for a darker Gothic timbre.
        lp = 0.62
        for i in range(1, total):
            left[i] = left[i] * lp + left[i - 1] * (1.0 - lp)
            right[i] = right[i] * lp + right[i - 1] * (1.0 - lp)

        return self._sound_from_stereo(left, right, sr)

    def _mix_plucked_string(
        self,
        left_samples: List[float],
        right_samples: List[float],
        start_index: int,
        midi_note: float,
        duration_sec: float,
        gain: float,
        pan: float = 0.0,
        seed: int = 0,
        brightness: float = 0.992,
    ) -> None:
        sr = self.sample_rate
        if sr <= 1000 or duration_sec <= 0.01 or start_index >= len(left_samples):
            return
        freq = self._midi_to_freq(int(round(float(midi_note))))
        if freq < 28.0:
            return
        buf_len = max(2, int(sr / freq))
        length = max(2, int(duration_sec * sr))
        rng = random.Random(seed + int(freq * 7.0))
        string_buf = [rng.uniform(-1.0, 1.0) for _ in range(buf_len)]
        idx = 0
        attack = max(1, int(sr * 0.012))
        pan_clamped = max(-0.95, min(0.95, float(pan)))
        theta = (pan_clamped + 1.0) * (math.pi / 4.0)
        left_gain = math.cos(theta)
        right_gain = math.sin(theta)
        smooth = 0.64
        prev = 0.0
        damp = max(0.90, min(0.9998, float(brightness)))

        for n in range(length):
            out_idx = start_index + n
            if out_idx >= len(left_samples):
                break
            raw = float(string_buf[idx])
            nxt = float(string_buf[(idx + 1) % buf_len])
            coupled = 0.5 * (raw + nxt)
            string_buf[idx] = coupled * damp
            idx = (idx + 1) % buf_len

            shaped = raw * smooth + prev * (1.0 - smooth)
            prev = shaped
            env_attack = 1.0 if n >= attack else (n / attack)
            env_decay = math.exp(-4.6 * (n / max(1, length)))
            pick = 0.0
            if n < attack:
                pick = (rng.random() * 2.0 - 1.0) * 0.12 * (1.0 - (n / attack))
            harmonic = math.sin(math.tau * freq * 2.0 * (n / sr)) * 0.05 * env_decay
            sample = (shaped * 0.90 + harmonic + pick) * env_attack * env_decay * float(gain)
            left_samples[out_idx] += sample * left_gain
            right_samples[out_idx] += sample * right_gain

    def _synth_theme(self, style: str) -> Optional[pygame.mixer.Sound]:
        if not self.enabled:
            return None
        sr = self.sample_rate
        if style == "town":
            # Dark Gothic Town: Slow, organ-like, minor key
            bpm = 60.0
            # Cm, Ab, Fm, G (i - VI - iv - V)
            progression = [
                [48, 51, 55], # Cm
                [44, 48, 51], # Ab
                [41, 44, 48], # Fm
                [43, 47, 50], # G
            ]
            base_gain = 0.30
        else:
            # Wilderness: Deep, unsettling drone
            bpm = 48.0
            # Low clusters
            progression = [
                [36, 43, 48], # C + G + C
                [34, 41, 46], # Bb + F + Bb
                [32, 39, 44], # Ab + Eb + Ab
                [31, 38, 43], # G + D + G
            ]
            base_gain = 0.28

        beat_len = 60.0 / bpm
        bar_len = beat_len * 4.0
        duration = bar_len * len(progression) * 2.0 # 2 loops
        total = max(8, int(duration * sr))
        fade_len = int(sr * 0.5)
        samples = array("h")
        
        for i in range(total):
            t = i / sr
            bar_idx = int(t / bar_len) % len(progression)
            chord = progression[bar_idx]
            
            # LFO for movement
            lfo = math.sin(math.tau * 0.2 * t)

            if style == "town":
                # Organ-ish additive synthesis
                tone = 0.0
                for note in chord:
                    freq = self._midi_to_freq(note)
                    # Fundamental + Octave + 12th (Octave+5th)
                    tone += math.sin(math.tau * freq * t) * 0.5
                    tone += math.sin(math.tau * freq * 2.0 * t) * 0.25
                    tone += math.sin(math.tau * freq * 3.0 * t) * 0.12
                
                # Add a slight detuned layer for "choir" effect
                tone += math.sin(math.tau * self._midi_to_freq(chord[0] + 12) * 1.01 * t) * 0.1
                
                # Normalize roughly based on note count
                tone /= len(chord)
                
            else:
                # Wilderness: Dark Drone
                tone = 0.0
                # Deep bass drone (Saw-like approximation)
                root_freq = self._midi_to_freq(chord[0])
                # Sawtooth approximation: sum of sin(n*f)/n
                for h in range(1, 6):
                    tone += (math.sin(math.tau * root_freq * h * t) / h) * 0.6
                
                # Eerie high pitch wind
                wind_freq = self._midi_to_freq(chord[2] + 24) # High note
                tone += math.sin(math.tau * wind_freq * t + lfo) * 0.15
                
                # Unsettling pulse
                pulse = math.sin(math.tau * 4.0 * t) * 0.1
                tone *= (1.0 + pulse)

            env = 1.0
            if i < fade_len:
                env *= i / max(1, fade_len)
            if i > total - fade_len:
                env *= max(0.0, (total - i) / max(1, fade_len))
            amp = max(-1.0, min(1.0, tone * env * base_gain))
            samples.append(int(amp * 32767.0))
        return self._sound_from_mono(samples, sr)

    def _load_sound_file(self, relative_path: str) -> Optional[pygame.mixer.Sound]:
        if not self.enabled:
            return None
        path = os.path.join(self.sound_root, relative_path)
        if not os.path.exists(path):
            return None
        try:
            return pygame.mixer.Sound(path)
        except pygame.error:
            return None

    def _add_external_sound(self, key: str, relative_path: str, volume: float) -> bool:
        snd = self._load_sound_file(relative_path)
        if not isinstance(snd, pygame.mixer.Sound):
            return False
        snd.set_volume(max(0.0, min(1.0, float(volume))))
        self.sfx[key] = snd
        return True

    def _load_first_sound(self, relative_paths: List[str], volume: float) -> Optional[pygame.mixer.Sound]:
        for rel in relative_paths:
            snd = self._load_sound_file(rel)
            if not isinstance(snd, pygame.mixer.Sound):
                continue
            snd.set_volume(max(0.0, min(1.0, float(volume))))
            return snd
        return None

    def _load_theme_music_file(self, relative_path: str, volume: float) -> Optional[pygame.mixer.Sound]:
        if not self.enabled:
            return None
        path = os.path.join(self.theme_music_root, relative_path)
        if not os.path.exists(path):
            return None
        try:
            snd = pygame.mixer.Sound(path)
        except pygame.error:
            return None
        snd.set_volume(max(0.0, min(1.0, float(volume))))
        return snd

    def _add_external_variants(self, key: str, relative_paths: List[str], volume: float) -> bool:
        variants: List[pygame.mixer.Sound] = []
        for rel in relative_paths:
            snd = self._load_sound_file(rel)
            if isinstance(snd, pygame.mixer.Sound):
                snd.set_volume(max(0.0, min(1.0, float(volume))))
                variants.append(snd)
        if variants:
            self.sfx_variants[key] = variants
            # Keep a default entry for systems that inspect self.sfx directly.
            self.sfx[key] = variants[0]
            return True
        return False

    def _load_external_audio_pack(self) -> bool:
        # Curated for Sangeroasa's dark medieval tone: harpsichord cues + gritty foley/combat.
        town_music = self._load_theme_music_file(os.path.join("town", "Cathedral of Broken Crowns.mp3"), 0.34)
        if not isinstance(town_music, pygame.mixer.Sound):
            town_music = self._load_first_sound([
                os.path.join("Musical Effects", "grand_piano_inn.wav"),
                os.path.join("Musical Effects", "harpsichord_inn.wav"),
                os.path.join("Musical Effects", "music_box_inn.wav"),
                os.path.join("Musical Effects", "brass_inn.wav"),
            ], 0.34)
        wild_music = self._load_theme_music_file(os.path.join("wildernes", "Gallows Orchard.mp3"), 0.32)
        if not isinstance(wild_music, pygame.mixer.Sound):
            wild_music = self._load_first_sound([
                os.path.join("Musical Effects", "music_box_mystery.wav"),
                os.path.join("Musical Effects", "grand_piano_mystery.wav"),
                os.path.join("Musical Effects", "harpsichord_mystery.wav"),
                os.path.join("Musical Effects", "synth_bass_mystery.wav"),
            ], 0.32)
        if isinstance(town_music, pygame.mixer.Sound):
            self.music["town"] = town_music
        if isinstance(wild_music, pygame.mixer.Sound):
            self.music["wilderness"] = wild_music

        town_amb = self._load_first_sound([
            os.path.join("Environment", "water_babbling_loop.wav"),
            os.path.join("Environment", "fire_lighting.wav"),
        ], 0.16)
        wild_amb = self._load_first_sound([
            os.path.join("Other", "white_noise_long.wav"),
            os.path.join("Environment", "gurgling.wav"),
            os.path.join("Environment", "water_dripping.wav"),
        ], 0.14)
        if isinstance(town_amb, pygame.mixer.Sound):
            self.ambience["town"] = town_amb
        if isinstance(wild_amb, pygame.mixer.Sound):
            self.ambience["wilderness"] = wild_amb

        loaded = 0
        loaded += int(self._add_external_variants("ui_open", [
            os.path.join("UI", "select_1.wav"),
            os.path.join("UI", "select_2.wav"),
            os.path.join("UI", "select_3.wav"),
        ], 0.36))
        loaded += int(self._add_external_variants("ui_close", [
            os.path.join("UI", "cancel.wav"),
            os.path.join("UI", "toggle_off.wav"),
        ], 0.34))
        loaded += int(self._add_external_variants("ui_error", [
            os.path.join("UI", "cancel.wav"),
            os.path.join("UI", "synth_error.wav"),
        ], 0.34))

        loaded += int(self._add_external_variants("cast_projectile", [
            os.path.join("Other", "whoosh_1.wav"),
            os.path.join("Other", "whoosh_2.wav"),
            os.path.join("Environment", "air_burst.wav"),
        ], 0.42))
        loaded += int(self._add_external_variants("cast_nova", [
            os.path.join("Environment", "air_burst.wav"),
            os.path.join("Other", "ghost_long.wav"),
        ], 0.38))
        loaded += int(self._add_external_variants("cast_orb", [
            os.path.join("Other", "whoosh_2.wav"),
            os.path.join("Other", "ghost_long.wav"),
        ], 0.40))
        loaded += int(self._add_external_variants("cast_ward", [
            os.path.join("Musical Effects", "horror_sting.wav"),
            os.path.join("Other", "ghost_long.wav"),
        ], 0.34))
        loaded += int(self._add_external_variants("cast_melee", [
            os.path.join("Weapons", "sword_slice.wav"),
            os.path.join("Weapons", "sword_clash.wav"),
            os.path.join("Weapons", "sword_clash_2.wav"),
        ], 0.50))
        loaded += int(self._add_external_sound("target_lock", os.path.join("Environment", "lock_lock.wav"), 0.32))

        loaded += int(self._add_external_sound("loot_open", os.path.join("Environment", "lock_unlock.wav"), 0.34))
        loaded += int(self._add_external_variants("loot_pick", [
            os.path.join("Items", "coin_collect.wav"),
            os.path.join("Items", "coin_jingle_small.wav"),
            os.path.join("Items", "coins_gather_small.wav"),
        ], 0.34))
        loaded += int(self._add_external_variants("loot_all", [
            os.path.join("Items", "coins_gather_medium.wav"),
            os.path.join("Items", "coins_gather_quick.wav"),
            os.path.join("Items", "gem_collect.wav"),
        ], 0.36))

        loaded += int(self._add_external_variants("portal", [
            os.path.join("Other", "ghost_long.wav"),
            os.path.join("Musical Effects", "horror_sting.wav"),
        ], 0.42))

        loaded += int(self._add_external_sound("quest_accept", os.path.join("Musical Effects", "harpsichord_level_start.wav"), 0.36))
        loaded += int(self._add_external_sound("quest_complete", os.path.join("Musical Effects", "harpsichord_level_complete.wav"), 0.38))
        loaded += int(self._add_external_sound("quest_turnin", os.path.join("Musical Effects", "harpsichord_chime_positive.wav"), 0.36))

        loaded += int(self._add_external_sound("craft", os.path.join("Weapons", "weapon_upgrade.wav"), 0.40))
        loaded += int(self._add_external_sound("buy", os.path.join("Items", "coin_jingle_small.wav"), 0.34))
        loaded += int(self._add_external_variants("equip", [
            os.path.join("Weapons", "weapon_equip_short.wav"),
            os.path.join("Items", "item_equip.wav"),
        ], 0.38))

        loaded += int(self._add_external_variants("player_hit", [
            os.path.join("Combat and Gore", "crunch.wav"),
            os.path.join("Combat and Gore", "crunch_splat.wav"),
            os.path.join("Combat and Gore", "punch_3.wav"),
        ], 0.42))
        loaded += int(self._add_external_variants("enemy_kill", [
            os.path.join("Combat and Gore", "bone_snap.wav"),
            os.path.join("Combat and Gore", "squelching_2.wav"),
            os.path.join("Combat and Gore", "splat_double_quick.wav"),
        ], 0.40))
        loaded += int(self._add_external_sound("level_up", os.path.join("Musical Effects", "harpsichord_positive_long.wav"), 0.40))
        loaded += int(self._add_external_sound("death", os.path.join("Musical Effects", "harpsichord_defeated.wav"), 0.44))

        loaded += int(self._add_external_variants("footstep_town", [
            os.path.join("Footsteps", "foley_footstep_concrete_1.wav"),
            os.path.join("Footsteps", "foley_footstep_concrete_2.wav"),
            os.path.join("Footsteps", "foley_footstep_concrete_3.wav"),
            os.path.join("Footsteps", "foley_footstep_concrete_4.wav"),
        ], 0.22))
        loaded += int(self._add_external_variants("footstep_wilderness", [
            os.path.join("Footsteps", "foley_footstep_gravel_1.wav"),
            os.path.join("Footsteps", "foley_footstep_gravel_2.wav"),
            os.path.join("Footsteps", "foley_footstep_gravel_3.wav"),
            os.path.join("Footsteps", "foley_footstep_gravel_4.wav"),
        ], 0.22))

        has_music = ("town" in self.music) and ("wilderness" in self.music)
        return loaded > 0 and has_music

    def init(self) -> None:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(28)
            pygame.mixer.set_reserved(3)
            self.music_channel = pygame.mixer.Channel(0)
            self.ui_channel = pygame.mixer.Channel(1)
            self.ambience_channel = pygame.mixer.Channel(2)
            self.enabled = True
        except pygame.error:
            self.enabled = False
            return

        self.sfx = {}
        self.sfx_variants = {}
        self.music = {}
        self.ambience = {}
        self.current_music = ""
        self.current_ambience = ""
        self.last_sfx_tick.clear()
        self.footstep_timer = 0.0
        self.using_external_audio_pack = self._load_external_audio_pack()

        if "town" not in self.music:
            town = self._synth_theme("town")
            if isinstance(town, pygame.mixer.Sound):
                town.set_volume(0.30)
                self.music["town"] = town
        if "wilderness" not in self.music:
            wild = self._synth_theme("wilderness")
            if isinstance(wild, pygame.mixer.Sound):
                wild.set_volume(0.28)
                self.music["wilderness"] = wild

        def add_synth(name: str, snd: Optional[pygame.mixer.Sound], volume: float = 0.6) -> None:
            if name in self.sfx:
                return
            if isinstance(snd, pygame.mixer.Sound):
                snd.set_volume(max(0.0, min(1.0, volume)))
                self.sfx[name] = snd

        add_synth("ui_open", self._synth_effect(0.16, 164, "triangle", sweep=0.26, volume=0.48, noise=0.02, vibrato_hz=3.0, vibrato_depth=0.03, punch=0.12, seed=111), 0.34)
        add_synth("ui_close", self._synth_effect(0.14, 146, "triangle", sweep=-0.28, volume=0.46, noise=0.02, vibrato_hz=2.0, vibrato_depth=0.03, punch=0.08, seed=112), 0.30)
        add_synth("ui_error", self._synth_effect(0.22, 84, "saw", sweep=-0.22, volume=0.52, noise=0.18, punch=0.36, seed=113), 0.38)
        add_synth("cast_projectile", self._synth_effect(0.24, 176, "saw", sweep=-0.18, volume=0.58, noise=0.06, vibrato_hz=6.0, vibrato_depth=0.05, punch=0.24, seed=121), 0.43)
        add_synth("cast_nova", self._synth_effect(0.34, 118, "square", sweep=-0.10, volume=0.60, noise=0.09, vibrato_hz=4.0, vibrato_depth=0.04, punch=0.40, seed=122), 0.44)
        add_synth("cast_orb", self._synth_effect(0.32, 142, "sine", sweep=0.08, volume=0.56, noise=0.05, vibrato_hz=4.8, vibrato_depth=0.10, punch=0.16, seed=123), 0.41)
        add_synth("cast_ward", self._synth_effect(0.36, 94, "triangle", sweep=0.14, volume=0.56, noise=0.06, vibrato_hz=2.6, vibrato_depth=0.07, punch=0.10, seed=124), 0.42)
        add_synth("cast_melee", self._synth_effect(0.18, 78, "square", sweep=-0.46, volume=0.60, noise=0.20, punch=0.62, seed=125), 0.44)
        add_synth("target_lock", self._synth_effect(0.11, 308, "sine", sweep=0.22, volume=0.44, noise=0.01, vibrato_hz=7.4, vibrato_depth=0.02, punch=0.20, seed=126), 0.30)
        add_synth("loot_open", self._synth_effect(0.14, 210, "triangle", sweep=-0.04, volume=0.44, noise=0.03, punch=0.08, seed=127), 0.33)
        add_synth("loot_pick", self._synth_effect(0.11, 248, "triangle", sweep=0.05, volume=0.40, noise=0.02, punch=0.05, seed=128), 0.31)
        add_synth("loot_all", self._synth_effect(0.20, 236, "triangle", sweep=0.18, volume=0.50, noise=0.04, punch=0.16, seed=129), 0.36)
        add_synth("portal", self._synth_effect(0.55, 86, "sine", sweep=1.10, volume=0.58, noise=0.10, vibrato_hz=4.2, vibrato_depth=0.12, punch=0.28, seed=130), 0.47)
        add_synth("quest_accept", self._synth_effect(0.24, 172, "triangle", sweep=0.22, volume=0.52, noise=0.03, vibrato_hz=3.0, vibrato_depth=0.03, punch=0.16, seed=131), 0.39)
        add_synth("quest_complete", self._synth_effect(0.30, 196, "sine", sweep=0.30, volume=0.56, noise=0.03, vibrato_hz=3.4, vibrato_depth=0.04, punch=0.20, seed=132), 0.42)
        add_synth("quest_turnin", self._synth_effect(0.34, 228, "sine", sweep=0.36, volume=0.58, noise=0.04, vibrato_hz=3.8, vibrato_depth=0.06, punch=0.24, seed=133), 0.44)
        add_synth("craft", self._synth_effect(0.22, 132, "triangle", sweep=-0.06, volume=0.52, noise=0.10, punch=0.22, seed=134), 0.39)
        add_synth("buy", self._synth_effect(0.14, 286, "sine", sweep=0.12, volume=0.44, noise=0.01, punch=0.08, seed=135), 0.33)
        add_synth("equip", self._synth_effect(0.18, 158, "square", sweep=-0.12, volume=0.54, noise=0.08, punch=0.24, seed=136), 0.38)
        add_synth("player_hit", self._synth_effect(0.22, 62, "saw", sweep=-0.20, volume=0.58, noise=0.24, punch=0.50, seed=137), 0.41)
        add_synth("enemy_kill", self._synth_effect(0.25, 76, "square", sweep=-0.36, volume=0.56, noise=0.16, punch=0.36, seed=138), 0.39)
        add_synth("level_up", self._synth_effect(0.48, 188, "sine", sweep=0.62, volume=0.60, noise=0.03, vibrato_hz=4.2, vibrato_depth=0.08, punch=0.20, seed=139), 0.47)
        add_synth("death", self._synth_effect(0.64, 52, "triangle", sweep=-0.42, volume=0.60, noise=0.22, vibrato_hz=1.8, vibrato_depth=0.03, punch=0.34, seed=140), 0.46)

    def play_sfx(self, name: str, cooldown_ms: int = 0) -> None:
        if not self.enabled:
            return
        key = str(name)
        variants = self.sfx_variants.get(key, [])
        sound: Optional[pygame.mixer.Sound] = None
        if variants:
            sound = random.choice(variants)
        else:
            sound = self.sfx.get(key)
        if not isinstance(sound, pygame.mixer.Sound):
            return
        now = pygame.time.get_ticks()
        if cooldown_ms > 0:
            last = self.last_sfx_tick.get(key, -999999)
            if now - last < cooldown_ms:
                return
            self.last_sfx_tick[key] = now
        channel: Optional[pygame.mixer.Channel]
        if key.startswith("ui_") or key in ("loot_open", "loot_pick", "loot_all", "target_lock"):
            channel = self.ui_channel
        else:
            channel = pygame.mixer.find_channel(False)
            if channel is None:
                channel = pygame.mixer.find_channel(True)
        if channel is not None:
            channel.play(sound)

    def play_music(self, track: str, fade_ms: int = 800) -> None:
        if not self.enabled:
            return
        song = self.music.get(str(track))
        if not isinstance(song, pygame.mixer.Sound):
            return
        if self.current_music == track and self.music_channel is not None and self.music_channel.get_busy():
            return
        self.current_music = str(track)
        if self.music_channel is None:
            self.music_channel = pygame.mixer.Channel(0)
        self.music_channel.play(song, loops=-1, fade_ms=max(0, int(fade_ms)))

    @staticmethod
    def _level_track(level_name: str) -> str:
        return "town" if str(level_name).strip().lower() == "town" else "wilderness"

    def ensure_level_theme(self, level_name: str, force: bool = False) -> None:
        if not self.enabled:
            return
        track = self._level_track(level_name)
        music_busy = self.music_channel is not None and self.music_channel.get_busy()
        ambience_busy = self.ambience_channel is not None and self.ambience_channel.get_busy()
        if force or self.current_music != track or not music_busy:
            self.play_music(track, fade_ms=220 if force else 900)
        if force or self.current_ambience != track or not ambience_busy:
            self.sync_ambience(track)

    def sync_music(self, level_name: str) -> None:
        self.ensure_level_theme(level_name, force=False)

    def sync_ambience(self, level_name: str) -> None:
        if not self.enabled:
            return
        track = self._level_track(level_name)
        if self.current_ambience == track and self.ambience_channel is not None and self.ambience_channel.get_busy():
            return
        snd = self.ambience.get(track)
        if not isinstance(snd, pygame.mixer.Sound):
            if self.ambience_channel is not None:
                self.ambience_channel.fadeout(260)
            self.current_ambience = ""
            return
        if self.ambience_channel is None:
            self.ambience_channel = pygame.mixer.Channel(2)
        self.current_ambience = track
        self.ambience_channel.play(snd, loops=-1, fade_ms=1000)

    def update_footsteps(self, dt: float, moving: bool, level_name: str, sprinting: bool = False) -> None:
        if not self.enabled:
            return
        if dt <= 0.0 or not moving:
            self.footstep_timer = 0.0
            return
        self.footstep_timer -= float(dt)
        if self.footstep_timer > 0.0:
            return
        if str(level_name) == "town":
            cue = "footstep_town"
            base_interval = 0.31
        else:
            cue = "footstep_wilderness"
            base_interval = 0.28
        if sprinting:
            base_interval *= 0.82
        self.play_sfx(cue, cooldown_ms=0)
        self.footstep_timer = max(0.10, base_interval * random.uniform(0.86, 1.16))

    def play_status(self, text: str) -> None:
        lower = str(text).strip().lower()
        if not lower:
            return
        if "quest accepted" in lower:
            self.play_sfx("quest_accept", cooldown_ms=120)
        elif "quest complete" in lower:
            self.play_sfx("quest_complete", cooldown_ms=160)
        elif "turned in:" in lower:
            self.play_sfx("quest_turnin", cooldown_ms=180)
        elif "skill tree opened" in lower:
            self.play_sfx("ui_open", cooldown_ms=70)
        elif "crafted " in lower:
            self.play_sfx("craft", cooldown_ms=90)
        elif "bought " in lower:
            self.play_sfx("buy", cooldown_ms=90)
        elif "equipped " in lower:
            self.play_sfx("equip", cooldown_ms=90)
        elif "defeated " in lower and "wolf" in lower:
            self.play_sfx("enemy_kill", cooldown_ms=110)
        elif "looted:" in lower:
            self.play_sfx("loot_all", cooldown_ms=80)
        elif lower.startswith("looted "):
            self.play_sfx("loot_pick", cooldown_ms=50)
        elif "inventory full" in lower or "not enough" in lower or "locked" in lower:
            self.play_sfx("ui_error", cooldown_ms=120)
        elif "the portal opens" in lower or "through the portal" in lower or "town portal scroll opened" in lower:
            self.play_sfx("portal", cooldown_ms=240)
        elif "level up!" in lower:
            self.play_sfx("level_up", cooldown_ms=240)
        elif "wolves hit you" in lower:
            self.play_sfx("player_hit", cooldown_ms=120)
        elif "you fell in the wilderness" in lower:
            self.play_sfx("death", cooldown_ms=260)
