import sys, os, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from check_figures import check_item, check_svg

GOOD_SVG = (
    '<svg viewBox="0 0 720 400" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="10" y="10" width="200" height="80" fill="none" stroke="#333333"/>'
    '<text x="110" y="55" font-size="18" fill="#cf5a3c" text-anchor="middle">the point</text>'
    '</svg>'
)


def item_with(svg, caption="cap"):
    return {"overview": {"sections": [{"heading": "main contribution", "blocks": [
        {"type": "figure", "svg": svg, "caption": caption}]}]}}


def test_good_figure_passes():
    rep = check_item(item_with(GOOD_SVG))
    assert rep["ok"], rep
    assert rep["figures"] == 1


def test_missing_viewbox_is_error():
    errors, _ = check_svg('<svg><text x="0" y="20" font-size="18">hi</text></svg>', "f")
    assert any("viewBox" in e for e in errors)


def test_too_tall_viewbox_is_error():
    errors, _ = check_svg('<svg viewBox="0 0 720 620"></svg>', "f")
    assert any("420" in e for e in errors)


def test_off_palette_color_is_error():
    svg = '<svg viewBox="0 0 720 300"><rect fill="#ff0000"/></svg>'
    errors, _ = check_svg(svg, "f")
    assert any("#ff0000" in e for e in errors)


def test_small_font_and_font_family_are_errors():
    svg = ('<svg viewBox="0 0 720 300">'
           '<text x="0" y="20" font-size="11" font-family="Arial" fill="#333333">x</text></svg>')
    errors, _ = check_svg(svg, "f")
    assert any("font-size 11" in e for e in errors)
    assert any("font-family" in e for e in errors)


def test_stripped_elements_are_errors():
    svg = '<svg viewBox="0 0 720 300"><foreignObject/><image href="http://x/y.png"/></svg>'
    errors, _ = check_svg(svg, "f")
    assert any("foreignObject" in e for e in errors)


def test_text_overflow_is_warning():
    svg = ('<svg viewBox="0 0 720 300"><text x="700" y="20" font-size="18" '
           'fill="#333333">a label far too long to fit at that x</text></svg>')
    _, warnings = check_svg(svg, "f")
    assert any("overflow" in w for w in warnings)


def test_no_figure_contract():
    rep = check_item({"overview": {"sections": []}})
    assert not rep["ok"]
    rep = check_item({"overview": {"no_figure": {"reason": "nothing structural"},
                                   "sections": []}})
    assert rep["ok"]
    both = item_with(GOOD_SVG)
    both["overview"]["no_figure"] = {"reason": "oops"}
    rep = check_item(both)
    assert any("no_figure is set but figures exist" in e for e in rep["errors"])


def test_missing_caption_is_error():
    rep = check_item(item_with(GOOD_SVG, caption=""))
    assert any("caption" in e for e in rep["errors"])


from check_figures import fix_item, fix_svg


def test_fix_snaps_off_palette_hex_to_nearest_theme_color():
    svg = '<svg viewBox="0 0 720 300"><rect fill="#ff2200" stroke="#343434"/></svg>'
    fixed, fixes = fix_svg(svg)
    assert 'fill="#cf5a3c"' in fixed        # reddish -> coral
    assert 'stroke="#333333"' in fixed      # near-ink -> ink
    assert len(fixes) == 2


def test_fix_clamps_small_font_sizes():
    svg = ('<svg viewBox="0 0 720 300"><text font-size="11" fill="#333333">x</text>'
           '<text style="font-size:12px" fill="#333333">y</text></svg>')
    fixed, fixes = fix_svg(svg)
    assert 'font-size="16"' in fixed and "font-size:16" in fixed
    assert len(fixes) == 2


def test_fix_leaves_palette_colors_and_named_colors_alone():
    svg = '<svg viewBox="0 0 720 300"><rect fill="#cf5a3c" stroke="none"/><circle fill="red"/></svg>'
    fixed, fixes = fix_svg(svg)
    assert fixed == svg and fixes == []     # 'red' stays -> still a lint error


def test_fix_item_repairs_figures_so_check_passes():
    item = item_with('<svg viewBox="0 0 720 300" xmlns="http://www.w3.org/2000/svg">'
                     '<text x="10" y="30" font-size="12" fill="#e06040">label</text></svg>')
    fixes = fix_item(item)
    assert fixes
    rep = check_item(item)
    assert rep["ok"], rep
