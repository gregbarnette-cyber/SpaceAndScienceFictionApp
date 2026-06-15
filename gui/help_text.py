"""Phase O — help/explanation text constants (GUI layer).

Plain rich-text (QTextBrowser-compatible HTML) shown by the reusable help dialog in
``gui/help.py``. Kept separate from logic so wording edits don't touch code.

First entry: O11 (Toomre / Galactic Kinematics) — the explanation behind the
"ℹ What is this?" button on the Kinematics tab (opts 1, 3–6, 8).
"""

TOOMRE_HELP_HTML = """
<h3>Toomre / Galactic Kinematics Diagram</h3>

<h4>What it is</h4>
<p>The standard plot for reading a star's Galactic motion. It turns the three
space-velocity components Hypatia returns &mdash; <b>U</b> (toward the Galactic
centre), <b>V</b> (along Galactic rotation) and <b>W</b> (toward the north Galactic
pole) &mdash; into a 2-D view that reveals which stellar <b>population</b> the star
belongs to.</p>

<h4>The axes</h4>
<p><b>x = V</b> (rotational velocity). <b>y = &#8730;(U&#178; + W&#178;)</b> &mdash; the
two non-rotational components combined into one &ldquo;perpendicular speed&rdquo;. A
star's total space velocity is &#8730;(U&#178;+V&#178;+W&#178;), so <b>lines of
constant total speed are circles</b> on this plot.</p>

<h4>What the rings mean</h4>
<p>The dashed quarter-circles (50, 100, 180 km/s) are contours of constant total
velocity. The Galaxy's populations separate mostly by total speed, so the ring a star
sits inside tells you its population:</p>
<table border="1" cellpadding="5" cellspacing="0" width="100%">
  <tr><th align="left">Population</th><th align="left">Total speed</th><th align="left">Character</th></tr>
  <tr><td>Thin disk</td><td>&#8818; 50 km/s</td><td>young, metal-rich, near-circular orbits</td></tr>
  <tr><td>Thick disk</td><td>&#8776; 70&#8211;180</td><td>older, more eccentric / inclined</td></tr>
  <tr><td>Halo</td><td>&#8819; 180</td><td>ancient, metal-poor, plunging orbits</td></tr>
</table>

<h4>The marker</h4>
<p>The gold &#9733; is this star at its (V, &#8730;(U&#178;+W&#178;)) position; the
subtitle shows Hypatia's own <i>disk</i> classification so the geometric reading can be
cross-checked. The boundaries are <b>heuristic</b> &mdash; a probabilistic continuum,
not hard cuts.</p>
"""
