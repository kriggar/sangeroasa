"""One-shot script: replace the old draw_player_resource_bars function in main.py
with the helpers + no-op stub from _hud_new_block.py."""
import sys

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open('_hud_new_block.py', 'r', encoding='utf-8') as f:
    new_block = f.read()

START = 'def draw_player_resource_bars(\n    screen: pygame.Surface,'
# End marker is the last line of the function (the XP bar border rect draw)
END_MARKER = '        pygame.draw.rect(screen, (80, 60, 100), _xp_bar, 1, border_radius=2)\n'

start_idx = content.find(START)
if start_idx < 0:
    print("ERROR: START not found")
    sys.exit(1)

end_idx = content.find(END_MARKER, start_idx)
if end_idx < 0:
    print("ERROR: END_MARKER not found")
    sys.exit(1)
end_idx += len(END_MARKER)

# Sanity: make sure only one def draw_player_resource_bars in the whole file
occ = content.count('def draw_player_resource_bars(')
print(f"Found {occ} occurrence(s) of draw_player_resource_bars definition")
if occ != 1:
    print("ERROR: expected exactly 1 definition")
    sys.exit(1)

new_content = content[:start_idx] + new_block.rstrip('\n') + '\n' + content[end_idx:]

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Replaced {end_idx - start_idx} chars with {len(new_block)} chars")
print("OK")
