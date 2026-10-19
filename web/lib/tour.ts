// The tour's pages are designed at a fixed size (the PDF's), then scaled to fit the screen.
export const PAGE_W = 1080;
export const PAGE_H = 1350;

/**
 * Runs in <head> before the page paints: sets --tour-scale, the size that fits
 * a page in the window with room for the controls. The tour is part of the
 * server-rendered page, so it is there from the first frame, at the right size.
 */
export const TOUR_SCALE_SCRIPT = `(function(){function f(){var w=innerWidth,h=innerHeight,n=w<640;document.documentElement.style.setProperty("--tour-scale",String(Math.min((w-(n?24:96))/${PAGE_W},(h-(n?32:48))/${PAGE_H})))}f();addEventListener("resize",f)})()`;
