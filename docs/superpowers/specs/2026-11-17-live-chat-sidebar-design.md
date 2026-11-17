# Live chat sidebar: short design

Date: 2026-11-17.

- **Intent:** a right-hand column showing the conversations as they happen, like the chat next to a YouTube live video.
- **Goals:**
  - Each line appears when its bubble is shown on the map: the speaker's name in the character's colour, the emoji, then the text.
  - A separator when a pair meets ("Grillon croise Gérard").
  - At the end, a grey note per changed feeling ("Grillon ❤️ Gérard", "Gérard 😕 Grillon"), or "bof..." on an error.
  - Auto-scroll to the newest message, which pauses while the viewer has scrolled up and resumes at the bottom.
  - At most 200 messages are kept.
- **Non-goals:** no history on page load (live only, the user's choice), no backend change, no viewer input.
- **Layout:** the map on the left (the Phaser canvas fits its area), the sidebar on the right, about 320 px wide. On narrow screens (max 800 px) the sidebar goes under the map. The population slider stays over the map.
- **Approaches:** A, live only, picked by the user. B, history through a new `GET /api/conversations` endpoint, was not picked.
- **Left to the builder:** colours and spacing.
