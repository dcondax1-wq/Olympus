"""The page's EFFECTIVE background, as the eye sees it (QUALITY 2026-11-20).

OLYMPUS NIGHT paints the black on <html> (themes.js: rgb(4, 3, 5) + a soft glow) and leaves <body> transparent, so reading
getComputedStyle(document.body).backgroundColor alone gives 'rgba(0, 0, 0, 0)' on a page that is black on screen.
The effective colour = body's when it is not transparent, else <html>'s.  Same expression for Node: tests/page_bg.cjs.

    from tests.page_bg import PAGE_BG_JS, night_black
    bg = page.evaluate(PAGE_BG_JS)        # a CSS colour string
    night_black(bg)                       # True for rgb(0, 0, 0) / rgb(4, 3, 5)
"""
PAGE_BG_JS = ("(() => { const t = (c) => !c || c === 'transparent' || /rgba\\([^)]*,\\s*0\\)$/.test(c); "
              "const b = getComputedStyle(document.body).backgroundColor; "
              "return t(b) ? getComputedStyle(document.documentElement).backgroundColor : b; })()")
NIGHT_BLACKS = ("rgb(0, 0, 0)", "rgb(4, 3, 5)")


def night_black(bg: str) -> bool:
    """the OLYMPUS NIGHT page black: pure black or the theme engine's rgb(4, 3, 5)"""
    return (bg or "").strip() in NIGHT_BLACKS
