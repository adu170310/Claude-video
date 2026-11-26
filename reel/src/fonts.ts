import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const fontsReady = Promise.all([
  loadFont({ family: "Inter Display", url: staticFile("fonts/InterDisplay-Black.woff2"), weight: "900" }),
  loadFont({ family: "Poppins", url: staticFile("fonts/poppins-latin-500-normal.woff2"), weight: "500" }),
  loadFont({ family: "Poppins", url: staticFile("fonts/poppins-latin-600-normal.woff2"), weight: "600" }),
]);
