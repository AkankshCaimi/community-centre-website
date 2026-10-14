// The six pictures of the site (docs/specs/public-pages.md, Images). They are
// stand-ins: illustrations, not photographs of the centre (I1).
import dining from "./images/gallery-dining.jpg";
import foyer from "./images/gallery-foyer.jpg";
import stage from "./images/gallery-stage.jpg";
import exterior from "./images/hero-exterior.jpg";
import hall from "./images/hero-hall.jpg";
import kitchen from "./images/hero-kitchen.jpg";

export const NOTE = "The pictures on this site are illustrations and do not show our centre.";

export const EXTERIOR = {
  file: exterior,
  caption: "A centre from outside",
  alt: "A red-brick building with a glass entrance canopy and a lawn in front",
};
export const HALL = {
  file: hall,
  caption: "A hall laid out for a seated event",
  alt: "Round tables with white cloths and chairs fill a large room, with a curtained platform at the far end",
};
export const KITCHEN = {
  file: kitchen,
  caption: "A catering kitchen",
  alt: "Stainless-steel worktops, gas hobs and large cooking pots",
};
const DINING = {
  file: dining,
  caption: "A table laid for dinner",
  alt: "White linen, wine glasses, folded napkins and a centrepiece of white roses",
};
const FOYER = {
  file: foyer,
  caption: "A foyer",
  alt: "A reception desk, armchairs and potted plants in a bright room with tall windows",
};
const STAGE = {
  file: stage,
  caption: "A stage",
  alt: "Closed curtains, a wooden floor, a microphone stand and loudspeakers",
};

// In the order of the table in the spec (G1).
export const GALLERY = [EXTERIOR, HALL, KITCHEN, DINING, FOYER, STAGE];
