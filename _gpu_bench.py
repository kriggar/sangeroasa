"""GPU vs CPU sprite-rendering benchmark + proof frame.
GPU: moderngl instanced textured quads (one draw call for N sprites) + a post-FX shader.
CPU: pygame Surface.blit of the same N sprites.
Renders offscreen on the GPU, reports FPS for both, saves a proof PNG.
"""
import os, time, math, struct
import numpy as np
import moderngl
from PIL import Image
import pygame

W, H = 1280, 720
N = 4000           # sprites per frame
FRAMES = 120
SPR = "assets/rogue_anim/idle_down.png"

# ---------- load a real sprite (first cell) ----------
img = Image.open(SPR).convert("RGBA")
cell = img.height
img = img.crop((0, 0, cell, cell)).resize((64, 64), Image.LANCZOS)
tex_bytes = img.tobytes()

ctx = moderngl.create_standalone_context()
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

tex = ctx.texture((64, 64), 4, tex_bytes)
tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

prog = ctx.program(
    vertex_shader="""
    #version 330
    in vec2 in_quad;            // unit quad 0..1
    in vec2 i_pos;              // instance pixel pos
    in vec2 i_size;            // instance pixel size
    in vec4 i_col;             // instance tint
    uniform vec2 screen;
    out vec2 uv; out vec4 col;
    void main(){
        vec2 p = i_pos + in_quad * i_size;
        vec2 ndc = vec2(p.x/screen.x*2.0-1.0, 1.0-p.y/screen.y*2.0);
        gl_Position = vec4(ndc, 0.0, 1.0);
        uv = in_quad; col = i_col;
    }""",
    fragment_shader="""
    #version 330
    uniform sampler2D tex;
    in vec2 uv; in vec4 col; out vec4 f;
    void main(){ vec4 t = texture(tex, uv); f = t * col; }""",
)
prog["screen"].value = (W, H)

quad = np.array([0, 0, 1, 0, 0, 1, 1, 1], dtype="f4")
qbo = ctx.buffer(quad.tobytes())

rng = np.random.default_rng(0)
inst = np.zeros((N, 8), dtype="f4")
inst[:, 0] = rng.uniform(0, W - 64, N)      # x
inst[:, 1] = rng.uniform(0, H - 64, N)      # y
inst[:, 2] = 64                              # w
inst[:, 3] = 64                              # h
inst[:, 4:8] = rng.uniform(0.6, 1.0, (N, 4))
inst[:, 7] = 1.0
ibo = ctx.buffer(inst.tobytes())

vao = ctx.vertex_array(prog, [
    (qbo, "2f", "in_quad"),
    (ibo, "2f 2f 4f/i", "i_pos", "i_size", "i_col"),
])

# offscreen target + a post-FX (vignette + warm grade) pass
scene = ctx.texture((W, H), 4)
fbo = ctx.framebuffer(color_attachments=[scene])
post_prog = ctx.program(
    vertex_shader="""#version 330
    in vec2 p; out vec2 uv;
    void main(){ uv=(p+1.0)*0.5; gl_Position=vec4(p,0,1); }""",
    fragment_shader="""#version 330
    uniform sampler2D scene; in vec2 uv; out vec4 f;
    void main(){
        vec3 c = texture(scene, uv).rgb;
        float d = distance(uv, vec2(0.5));
        float vig = smoothstep(0.85, 0.35, d);     // vignette
        c *= vig; c *= vec3(1.06,1.0,0.92);        // warm grade
        f = vec4(c, 1.0);
    }""")
tri = np.array([-1, -1, 3, -1, -1, 3], dtype="f4")
post_vao = ctx.vertex_array(post_prog, [(ctx.buffer(tri.tobytes()), "2f", "p")])
screen_fbo = ctx.framebuffer(color_attachments=[ctx.texture((W, H), 4)])

# ---------- GPU timed loop ----------
ctx.finish()
t0 = time.perf_counter()
for fr in range(FRAMES):
    fbo.use(); fbo.clear(0.10, 0.09, 0.11, 1.0)
    tex.use(0); prog["tex"].value = 0
    vao.render(moderngl.TRIANGLE_STRIP, instances=N)
    screen_fbo.use(); scene.use(0); post_prog["scene"].value = 0
    post_vao.render(moderngl.TRIANGLES)
ctx.finish()
gpu_fps = FRAMES / (time.perf_counter() - t0)

# save proof frame
data = screen_fbo.read(components=4)
Image.frombytes("RGBA", (W, H), data).transpose(Image.FLIP_TOP_BOTTOM).save("assets_generated/rogue_build/_gpu_proof.png")

# ---------- CPU (pygame blit) comparison ----------
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.init()
pygame.display.set_mode((W, H))
surf = pygame.Surface((W, H)).convert()
spr = pygame.image.frombuffer(tex_bytes, (64, 64), "RGBA").convert_alpha()
pos = inst[:, :2].astype(int)
t0 = time.perf_counter()
CPU_FRAMES = 30
for fr in range(CPU_FRAMES):
    surf.fill((26, 23, 28))
    for i in range(N):
        surf.blit(spr, (pos[i, 0], pos[i, 1]))
cpu_fps = CPU_FRAMES / (time.perf_counter() - t0)

print(f"sprites/frame: {N}")
print(f"GPU (moderngl instanced + post-FX): {gpu_fps:6.1f} FPS")
print(f"CPU (pygame blit):                  {cpu_fps:6.1f} FPS")
print(f"speedup: {gpu_fps/cpu_fps:5.1f}x")
print("proof frame -> assets_generated/rogue_build/_gpu_proof.png")
