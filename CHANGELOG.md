# Changelog

## [1.1.2] - 2026-04-22
### Changed
- Fixed an issue where searches for valid albums or artists occasionally returned zero results due to overly restrictive API parameters
- Bypassed Apple's WAF safe-search filters that were silently hiding explicit albums
- Implemented cache-busting to prevent the iTunes CDN from continuously returning cached empty results
- Added browser User-Agent spoofing to prevent automated search requests from being throttled or blocked
- Optimized iTunes API queries to prioritize music media
- Updated all other project dependencies as needed

**Full Changelog**: https://github.com/SrikarC6/PureArt/compare/v1.1.1...v1.1.2


## [1.1.1] - 2026-04-16
### Changed
- Changed default quality selection to be low


## [1.1.0] - 2026-04-14
### Changed
- Added toggle for choosing low/medium/high quality album artwork downloads
- Welcome screen text now rendered in Textual Markdown widget from CSS
- Changed search selector widget from ListView to RadioButton
- Minor windowing changes to the welcome screen
- Updated all other dependencies as needed


## [1.0.3] - 2026-04-13
### Changed
- Changed Python environment management to uv
- Updated other dependencies as needed


## [1.0.2] - 2026-04-01
### Changed
- Updated PyFiglet logo
- Tightened padding on main screen for easier viewing on shorter screens
- Updated dependencies


## [1.0.1] - 2026-03-31
### Initial release