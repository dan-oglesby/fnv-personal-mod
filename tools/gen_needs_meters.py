"""Generate Needs Meters' HUD file: src/Needs Meters/menus/prefabs/NeedsMeters/NeedsMeters.xml

    python tools/gen_needs_meters.py      (build.py runs it first)

The HUD is a short block of rows (H2O, FOD, SLP, RAD, and PWR with Fission Power) at the right of
the screen, above the ammo counter. Each row is shown as a number, a meter, or both (setting _nmNum,
copied to the io traits _NMBars / _NMNums by Tick.txt):

- Numbers (_nmNum 1, the default): the raw value as the Pip-Boy counts it, e.g. "H2O 240" is 240
  dehydration points (rising as you get thirstier), "RAD 12" is 12 rads, "PWR 73 +2" is 73 percent
  charge and 2 spare batteries. The strings are built by Tick.txt (SetUIStringEx on the _NM...S
  traits).
- Meters (_nmNum 0, the old look): five segments, one per Hardcore stage (200 points each), drawn in
  the HUD colour like the vanilla HP and AP bars.
- Both (_nmNum 2): the meters with a number column after them.

In every mode a row switches to the HUD's alternate colour (the one the vanilla radiation meter
uses) at the stage where penalties start, and blinks at the critical stage.

- H2O, FOD and SLP drain as you get thirsty, hungry and tired. They are shown only in Hardcore mode.
- RAD fills as radiation builds, and is shown only while you have any.

Above the rows are up to three info lines, right-aligned with the block: the game clock (_nmClock: 1 =
12-hour, 2 = 24-hour, 0 = hidden); the weight you carry against what you can carry, "182/250 lb"
(_nmWeight 1, 2026-11-18), in the alternate colour while you carry more than that (_NMHeavy); and,
while the Mojave Heat mod runs, the temperature (_nmTemp 1; Mojave Heat publishes it on the player as
_mhTemp / _mhTempC and sets the non-saved *_mhLive while it ticks). The temperature turns the
alternate colour while heat is adding thirst (_NMHot). When the temperature line is hidden its slot
is the top one, so there is no visible gap. If the info lines
collide with something else at the top right in game, move the whole block with _nmY.

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
BLOCK_W = BAR_X + BAR_W  # the block's width with meters only (mode 0)
NUM_W = 48        # a number column: about 4 digits at font 7
NUM_GAP = 6       # space between the meters and the number column (mode 2)

# name, label, io trait, mode, warn at, crit at, number string trait. Modes: "drain" shows 1000 - value (needs, shown in
# Hardcore), "fill" shows the value (radiation, shown when above 0), "level" shows the value with
# warnings when it is LOW (power armor charge from Fission Power, 0-1000, shown when 0 or more, with
# the number of spare batteries after the bar).
ROWS = [
    ("NMWater", "H2O", "_NMWater", "drain", 400, 800, "_NMWaterS"),
    ("NMFood", "FOD", "_NMFood", "drain", 400, 800, "_NMFoodS"),
    ("NMSleep", "SLP", "_NMSleep", "drain", 400, 800, "_NMSleepS"),
    ("NMRads", "RAD", "_NMRads", "fill", 200, 800, "_NMRadsS"),
    ("NMPower", "PWR", "_NMPower", "level", 200, 100, "_NMPowerS"),
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
				<and src="io()" trait="_NMBars"/>
			</visible>
		</image>
"""


def number(warn, strait):
    """The parent row's value as a number, in the normal or the warning colour (modes 1 and 2)."""
    colour = "&hudalt;" if warn else "&hudmain;"
    show = "gte" if warn else "lt"
    return f"""		<text name="{'nw' if warn else 'n'}">
			<x><copy src="parent()" trait="_numx"/></x>
			<y> 0 </y>
			<font> 7 </font>
			<justify> &left; </justify>
			<systemcolor> {colour} </systemcolor>
			<string><copy src="io()" trait="{strait}"/></string>
			<alpha>
				<copy> 255 </copy>
				<sub>
					<copy> 160 </copy>
					<onlyif src="parent()" trait="_crit"/>
					<onlyif src="io()" trait="_NMBlink"/>
				</sub>
			</alpha>
			<visible>
				<copy src="parent()" trait="_warn"/>
				<{show}> 1 </{show}>
				<and src="io()" trait="_NMNums"/>
			</visible>
		</text>
"""


def info_row(n, name, strait, ontrait, hot=None):
    """A line above the rows (clock, weight, temperature), right-aligned with the block's right edge in
    every mode (longer strings grow leftward). With hot (a trait name, e.g. _NMHot), a paired tile in
    the alternate colour replaces it while io().<hot> is 1 (no blink)."""
    texts = []
    for warn in ([False, True] if hot else [False]):
        colour = "&hudalt;" if warn else "&hudmain;"
        vis = ""
        if hot:
            show = "gte" if warn else "lt"
            vis = f"""			<visible>
				<copy src="io()" trait="{hot}"/>
				<{show}> 1 </{show}>
			</visible>
"""
        texts.append(f"""		<text name="{'vw' if warn else 'v'}">
			<x><copy src="parent()" trait="width"/></x>
			<y> 0 </y>
			<font> 7 </font>
			<justify> &right; </justify>
			<systemcolor> {colour} </systemcolor>
			<string><copy src="io()" trait="{strait}"/></string>
{vis}		</text>
""")
    lblh = '<copy src="child(v)" trait="height"/>'
    if hot:
        lblh += '<max src="child(vw)" trait="height"/>'
    return f"""	<!-- {name} -->
	<rect name="{name}">
		<locus> &true; </locus>
		<x> 0 </x>
		<_lblh>{lblh}</_lblh>
		<y>
			<copy src="me()" trait="_lblh"/>
			<add src="io()" trait="_NMGap"/>
			<mul> {n} </mul>
		</y>
		<width><copy src="parent()" trait="width"/></width>
		<height><copy src="me()" trait="_lblh"/></height>
		<visible><copy src="io()" trait="{ontrait}"/></visible>
{"".join(texts)}	</rect>
"""


def row(n, name, label, trait, mode, warn_at, crit_at, strait):
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
			<visible>
				<copy src="io()" trait="_NMNums"/>
				<lt> 1 </lt>
			</visible>
		</text>
"""
    elif mode == "drain":
        fill = f"""<copy> 1000 </copy>
			<sub src="io()" trait="{trait}"/>"""
        shown = """<copy src="io()" trait="_NMHardcore"/>"""
    else:
        fill = f"""<copy src="io()" trait="{trait}"/>"""
        # 0.5 and up: the number would read at least 1, so a fraction of a rad shows no "RAD 0"
        shown = f"""<copy src="io()" trait="{trait}"/>
			<gte> 0.5 </gte>"""
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
			<visible><copy src="io()" trait="_NMBars"/></visible>
		</image>
""" for i in range(SEGS))
    segs = "".join(segment(i, False) + segment(i, True) for i in range(SEGS))
    nums = number(False, strait) + number(True, strait)
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
		<width><copy src="parent()" trait="width"/></width>
		<_numx><copy src="parent()" trait="_numx"/></_numx>
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
{backs}{segs}{nums}{extra}	</rect>
"""


def main():
    # info lines above the rows, top first: [temperature][weight][clock][H2O FOD SLP RAD PWR]
    rows = info_row(-3, "NMTemp", "_NMTempS", "_NMTempOn", "_NMHot")
    rows += info_row(-2, "NMWeight", "_NMWeightS", "_NMWeightOn", "_NMHeavy")
    rows += info_row(-1, "NMClock", "_NMClock", "_NMClockOn")
    rows += "".join(row(n, *r) for n, r in enumerate(ROWS))
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
<!-- Number strings, built by Tick.txt (SetUIStringEx): -->
<_NMWaterS> 0 </_NMWaterS>
<_NMFoodS> 0 </_NMFoodS>
<_NMSleepS> 0 </_NMSleepS>
<_NMRadsS> 0 </_NMRadsS>
<_NMPowerS> 0 </_NMPowerS>
<!-- Info lines: the clock, carried weight / capacity (_NMHeavy 1 while over it) and (with Mojave -->
<!-- Heat) the temperature; _NMHot 1 while heat adds thirst: -->
<_NMClock> 0 </_NMClock>
<_NMClockOn> 0 </_NMClockOn>
<_NMWeightS> 0 </_NMWeightS>
<_NMWeightOn> 0 </_NMWeightOn>
<_NMHeavy> 0 </_NMHeavy>
<_NMTempS> 0 </_NMTempS>
<_NMTempOn> 0 </_NMTempOn>
<_NMHot> 0 </_NMHot>
<!-- Settings, also set by Tick.txt from the player's saved settings: -->
<!-- display mode (_nmNum): meters _NMBars, numbers _NMNums; these defaults look like the old meters -->
<_NMBars> 1 </_NMBars>
<_NMNums> 0 </_NMNums>
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
	<!-- x of the number column: after the meters, or where they would start -->
	<_numx>
		<copy src="io()" trait="_NMBars"/>
		<mul> {BAR_W + NUM_GAP} </mul>
		<add> {BAR_X} </add>
	</_numx>
	<!-- {BLOCK_W} with meters only, {BAR_X + NUM_W} with numbers only, {BLOCK_W + NUM_GAP + NUM_W} with both -->
	<width>
		<copy src="io()" trait="_NMNums"/>
		<mul> {NUM_W + NUM_GAP} </mul>
		<add src="me()" trait="_numx"/>
		<sub> {NUM_GAP} </sub>
	</width>
	<height> {ROW_H * (len(ROWS) + 2)} </height>
	<x>
		<copy src="screen()" trait="width"/>
		<sub> 50 </sub>
		<sub src="me()" trait="width"/>
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
