# Asset provenance and licensing register

SP04 includes only source-authored SVG primitives and procedural test audio. No downloaded photograph, model, font, recording, station stream or brand logo is included. Rights to further third-party assets must be recorded before integration; the Owner must review recognizable product depictions and any trademark issues before commercial use. The following code paths are original implementation assets in this repository; distribution follows the repository's applicable terms, not a new third-party licence declaration.

| Group | ID / version | Origin / format | Status |
|---|---|---|---|
| Scene backgrounds | apartment, garage, beach, kindergarten_boat, card_club / v1 | SceneCanvas.tsx / responsive inline SVG | Original schematic; exact visual reference pending |
| Functional surfaces | table_round, table_square, table_felt, mat_blue, mat_striped, boat_deck, boat_bench / v1 | SceneCanvas.tsx / SVG | Original geometry |
| Decor | chair_wood, chair_metal, lamp, plant, bag, speaker_s50, cushion / v1 | SceneCanvas.tsx / SVG | Original stylized objects |
| Player skins | vesna_212s4, vega_122s_two_tier, mayak_233 / v1 | Stereo component / SVG | Stylized two-block Vega and separate S-50 pair; no photograph or logo |
| Recorded test sources | test_disco, test_retro / v1 | audio.ts / deterministic 8-second mono PCM WAV, 16 kHz | Original test tones, not commercial music |
| Melodia FM Disco | melodia_disco | Official broadcaster page: https://www.melodiafm.ua/online/ ; official player: https://play.tavr.media/melodiafm/disco/ | Online listening confirmed from official pages on 2026-11-27; direct stream and integration rights not established; disabled |
| Radio ROKS | radio_roks | Official broadcaster: https://www.radioroks.ua/online/ ; official player: https://play.tavr.media/radioroks/ | Online listening confirmed; rights and transport verification pending; disabled |
| Retro candidate | retro_radio | No confirmed operator-approved source | Disabled |

Source hashes (SHA-256 of supplied source files; use Git history for subsequent revisions):

- `frontend/src/decor/SceneCanvas.tsx`: `b26f4303c0816339dd42e080d828f814ebffbe6a016143d967682e277c133f66`
- `frontend/src/decor/audio.ts`: `d93aa67cdf41e345ca07dd177613718d03f9c2fe3fa542d9bdb55be9a0f653e3`
- `backend/src/sameplace/decor/catalog.py`: `8c07548526b58a214c980f86c29abebc1c382e12e47e10c81a06c338af599e01`

There is no server relay, stream caching, download service or paid provider. Before enabling a station: confirm operator permission and geographical/usage constraints, obtain the exact HTTPS media URL (not the player HTML), verify it plays in supported browsers and document the terms; do not include credentials or query secrets. Set the specific server env flags only after approval. Do not treat public availability as a licence. No change to production configuration in this candidate.
