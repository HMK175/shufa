# Style Sources

This directory is reserved for data used to estimate style profiles for the
isolated `llm_style_trajectory` experiment.

## fonts/

Put local `.ttf` or `.otf` font files here when you want to estimate a style
profile from font rendering. The build script also accepts absolute font paths
listed in `configs/style_sources.json`.

Recommended mapping examples:

- `kaishu`: regular script font
- `xingkai`: semi-cursive font
- `lishu`: clerical script font

No fonts are downloaded automatically.

## images/

Reserved for future image-sample based statistics. The current first version is
font-first because rendered font samples have cleaner and more consistent
geometry than loose image files.
