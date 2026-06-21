# game/world — level surfaces, portals, walk bounds, weather, day/night
# Target modules (to be extracted from main.py):
#   levels.py       — build_town(), build_wilderness(), build_ice_biome()
#   portals.py      — draw_town_portal, draw_ice_portal, portal logic
#   weather.py      — WeatherSystem, DayNightCycle (self-contained, good first candidate)
#   navigation.py   — build_nav_grid, pathfinding, nearest_walkable
