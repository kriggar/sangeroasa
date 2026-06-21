"""One-shot script: replace draw_spell_bar in main.py with the compact unified
action belt from _unified_bar_block.py."""
import sys

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open('_unified_bar_block.py', 'r', encoding='utf-8') as f:
    new_block = f.read()

START = 'def draw_spell_bar(\n    screen: pygame.Surface,\n    spellbook:'
END_MARKER = '        draw_hover_tooltip(_p_lines, passive_slot, ("passive", class_id))\n    return _slot_rects_out\n'

# Alternative end marker for the new unified version that returns a tuple
END_MARKER2 = '        draw_hover_tooltip(_p_lines, passive_slot, ("passive", class_id))\n    return _slot_rects_out, _pot_rects_out\n'

start_idx = content.find(START)
if start_idx < 0:
    print("ERROR: START not found")
    sys.exit(1)

# Try both end markers
end_idx = content.find(END_MARKER2, start_idx)
if end_idx >= 0:
    end_idx += len(END_MARKER2)
else:
    end_idx = content.find(END_MARKER, start_idx)
    if end_idx < 0:
        print("ERROR: END_MARKER not found")
        sys.exit(1)
    end_idx += len(END_MARKER)

occ = content.count('def draw_spell_bar(\n')
print(f"Found {occ} occurrence(s) of draw_spell_bar definition")
if occ != 1:
    print("ERROR: expected exactly 1 definition")
    sys.exit(1)

new_content = content[:start_idx] + new_block.rstrip('\n') + '\n' + content[end_idx:]

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Replaced {end_idx - start_idx} chars with {len(new_block)} chars")
print("OK")
