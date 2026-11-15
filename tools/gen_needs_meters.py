"""Generate Needs Meters' HUD file: src/Needs Meters/menus/prefabs/NeedsMeters/NeedsMeters.xml

    python tools/gen_needs_meters.py      (build.py runs it first)

The HUD is four short meters (H2O, FOD, SLP, RAD) at the right of the screen, above the ammo
counter. Each meter has five segments, one per Hardcore stage (200 points each). They are drawn in
the HUD colour like the vanilla HP and AP bars, switch to the HUD's alternate colour (the one the
vanilla radiation meter uses) at the stage where penalties start, and blink at the critical stage.

- H2O, FOD and SLP drain as you get thirsty, hungry and tired. They are shown only in Hardcore mode.
- RAD fills as radiation builds, and is shown only while you have any.

How it gets onto the HUD: UI Organizer reads Data\\uio\\public\\NeedsMeters.txt and injects this
file into the HUD when the game loads its menus. The game's own hud_main_menu.xml is never
replaced (Primary Needs HUD replaced it, which is what this replaces). Its values come from
Data\\nvse\\user_defined_functions\\NeedsMeters\\Tick.txt once a second, through SetUIFloat on the
_NM traits below, which become traits of HUDMainMenu itself.

Layout numbers follow the vanilla HUD and Primary Needs HUD, whose placement (right margin 50,
screen height / 1.3) is proven in game. Everything can be moved with the offsets _NMX / _NMY
(see README).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "Needs Meters" / "menus" / "prefabs" / "NeedsMeters" / "NeedsMeters.xml"

SEGS = 5          # one per Hardcore stage: 200 points each
SEG_W = 22
GAP = 3
BAR_X = 44        # labels are right-justified to x = 36
BAR_H = 8
ROW_H = 40           # used only for the block height estimate; rows are spaced by their labels
BAR_W = SEGS * SEG_W + (SEGS - 1) * GAP
BLOCK_W = BAR_X + BAR_W

# name, label, io trait, mode, warn at, crit at. Modes: "drain" shows 1000 - value (needs, shown in
# Hardcore), "fill" shows the value (radiation, shown when above 0), "level" shows the value with
# warnings when it is LOW (power armor charge from Fission Power, 0-1000, shown when 0 or more, with
# the number of spare batteries after the bar).
ROWS = [
    ("NMWater", "H2O", "_NMWater", "drain", 400, 800),
    ("NMFood", "FOD", "_NMFood", "drain", 400, 800),
    ("NMSleep", "SLP", "_NMSleep", "drain", 400, 800),
    ("NMRads", "RAD", "_NMRads", "fill", 200, 800),
    ("NMPower", "PWR", "_NMPower", "level", 200, 100),
]


def segment(i, warn):
    """One segment of the parent row's meter, in the normal or the warning colour."""
    lo = 200 * i
    colour = "&hudalt;" if warn else "&hudmain;"
    show = "gte" if warn else "lt"
    return f"""		<image name="{'w' if warn else 'f'}{i}">
			<filename> Interface\\Shared\\solid.dds </filename>
			<systemcolor> {colour} </systemcolor>
			<depth> 3 </depth>
			<x> {BAR_X + i * (SEG_W + GAP)} </x>
			<y>
				<copy src="parent()" trait="_lblh"/>
				<sub> {BAR_H} </sub>
				<div> 2 </div>
			</y>
			<height> {BAR_H} </height>
			<width>
				<copy src="parent()" trait="_fill"/>
				<sub> {lo} </sub>
				<div> 200 </div>
				<max> 0 </max>
				<min> 1 </min>
				<mul> {SEG_W} </mul>
			</width>
			<alpha>
				<copy> 230 </copy>
				<sub>
					<copy> 160 </copy>
					<onlyif src="parent()" trait="_crit"/>
					<onlyif src="io()" trait="_NMBlink"/>
				</sub>
			</alpha>
			<visible>
				<copy src="parent()" trait="_warn"/>
				<{show}> 1 </{show}>
			</visible>
		</image>
"""


def row(n, name, label, trait, mode, warn_at, crit_at):
    cmp = "lte" if mode == "level" else "gte"
    extra = ""
    if mode == "level":
        fill = f"""<copy src="io()" trait="{trait}"/>"""
        shown = f"""<copy src="io()" trait="{trait}"/>
			<gte> 0 </gte>"""
        extra = f"""		<text name="spare">
			<x> {BAR_X + BAR_W + 6} </x>
			<y> 0 </y>
			<font> 7 </font>
			<justify> &left; </justify>
			<string><copy src="io()" trait="_NMBatt"/></string>
		</text>
"""
    elif mode == "drain":
        fill = f"""<copy> 1000 </copy>
			<sub src="io()" trait="{trait}"/>"""
        shown = """<copy src="io()" trait="_NMHardcore"/>"""
    else:
        fill = f"""<copy src="io()" trait="{trait}"/>"""
        shown = f"""<copy src="io()" trait="{trait}"/>
			<gt> 0 </gt>"""
    backs = "".join(f"""		<image name="b{i}">
			<filename> Interface\\Shared\\solid.dds </filename>
			<depth> 2 </depth>
			<x> {BAR_X + i * (SEG_W + GAP)} </x>
			<y>
				<copy src="parent()" trait="_lblh"/>
				<sub> {BAR_H} </sub>
				<div> 2 </div>
			</y>
			<width> {SEG_W} </width>
			<height> {BAR_H} </height>
			<alpha> 48 </alpha>
		</image>
""" for i in range(SEGS))
    segs = "".join(segment(i, False) + segment(i, True) for i in range(SEGS))
    return f"""	<!-- {label} -->
	<rect name="{name}">
		<locus> &true; </locus>
		<x> 0 </x>
		<_lblh><copy src="child(lbl)" trait="height"/></_lblh>
		<y>
			<copy src="me()" trait="_lblh"/>
			<add src="io()" trait="_NMGap"/>
			<mul> {n} </mul>
		</y>
		<width> {BLOCK_W} </width>
		<height><copy src="me()" trait="_lblh"/></height>
		<visible>
			{shown}
		</visible>
		<_need><copy src="io()" trait="{trait}"/></_need>
		<_fill>
			{fill}
		</_fill>
		<_warn>
			<copy src="me()" trait="_need"/>
			<{cmp}> {warn_at} </{cmp}>
		</_warn>
		<_crit>
			<copy src="me()" trait="_need"/>
			<{cmp}> {crit_at} </{cmp}>
		</_crit>
		<text name="lbl">
			<x> 36 </x>
			<y> 0 </y>
			<font> 7 </font>
			<justify> &right; </justify>
			<string> {label} </string>
			<alpha>
				<copy> 255 </copy>
				<sub>
					<copy> 160 </copy>
					<onlyif src="parent()" trait="_crit"/>
					<onlyif src="io()" trait="_NMBlink"/>
				</sub>
			</alpha>
		</text>
{backs}{segs}{extra}	</rect>
"""


def main():
    rows = "".join(row(n, *r) for n, r in enumerate(ROWS))
    xml = f"""<!-- NeedsMeters.xml: generated by tools/gen_needs_meters.py; edit that, not this file. -->
<!-- Needs Meters (fnv-personal-mod): injected into HUDMainMenu by UI Organizer. -->
<!-- Values, set once a second by NeedsMeters/Tick.txt (raw actor values, 0-1000+): -->
<_NMWater> 0 </_NMWater>
<_NMFood> 0 </_NMFood>
<_NMSleep> 0 </_NMSleep>
<_NMRads> 0 </_NMRads>
<_NMHardcore> 0 </_NMHardcore>
<_NMBlink> 0 </_NMBlink>
<_NMPower> -1 </_NMPower>
<_NMBatt> 0 </_NMBatt>
<!-- Settings, also set by Tick.txt from the player's saved settings: -->
<_NMOn> 1 </_NMOn>
<_NMX> 0 </_NMX>
<_NMGap> 10 </_NMGap>
<_NMY> 0 </_NMY>

<rect name="NeedsMeters">
	<id> &noglow_branch; </id>
	<systemcolor> &hudmain; </systemcolor>
	<locus> &true; </locus>
	<visible>
		<copy src="io()" trait="_NMOn"/>
		<and src="ActionPoints" trait="visible"/>
	</visible>
	<width> {BLOCK_W} </width>
	<height> {ROW_H * len(ROWS)} </height>
	<x>
		<copy src="screen()" trait="width"/>
		<sub> 50 </sub>
		<sub> {BLOCK_W} </sub>
		<add src="io()" trait="_NMX"/>
	</x>
	<y>
		<copy src="screen()" trait="height"/>
		<div> 1.3 </div>
		<sub> 230 </sub>
		<add src="io()" trait="_NMY"/>
	</y>
{rows}</rect>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(xml, encoding="utf-8", newline="\r\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
