---
stage: model
bolt: 082-full-width-stream
created: 2026-09-23T15:43:35Z
---

# Full-width stream model

- **Login window geometry** (runner-owned): for every login device the remote Chromium window is
  fullscreen inside its Xvfb framebuffer and the page viewport equals the framebuffer
  (`LoginDevice.display_size`, 480x960 mobile / 1280x800 desktop). The mobile context keeps the
  server-owned Android profile (user agent, touch, scale factor); only viewport and screen size
  change. Cookies and capture do not depend on viewport size.
- **Stream presentation** (viewer-owned): on touch phones the stream is scaled to the viewer's
  full width and scrolled vertically (the 1:2 framebuffer is taller than the area); desktop logins
  fit to screen. Presentation never reads page content and is not identity evidence.
- **Chrome budget**: status is one compact line, help collapses behind a header control, the dock
  is one row. The remaining height belongs to the stream.
