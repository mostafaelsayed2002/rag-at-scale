/** Where the reader's light/dark choice is kept. */
export const THEME_STORAGE_KEY = "theme";

/**
 * Runs in <head> before the page paints: applies the saved theme, so a reader
 * who chose dark does not see a white flash on every load. Without a saved
 * choice the system setting applies (globals.css).
 */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
