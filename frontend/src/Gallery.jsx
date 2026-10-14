import { GALLERY, NOTE } from "./pictures.js";

// The gallery: here the pictures are the content (docs/specs/public-pages.md, G1, I4).
export default function Gallery() {
  return (
    <>
      <h1>Gallery</h1>
      <p>{NOTE}</p>
      {GALLERY.map((picture) => (
        <figure key={picture.caption}>
          <img src={picture.file} alt={picture.alt} width="1536" height="864" />
          <figcaption>{picture.caption}</figcaption>
        </figure>
      ))}
    </>
  );
}
