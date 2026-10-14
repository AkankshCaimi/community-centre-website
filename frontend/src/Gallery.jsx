import { GALLERY, NOTE } from "./pictures.js";

// The gallery: here the pictures are the content (docs/specs/public-pages.md, G1, I4).
export default function Gallery() {
  return (
    <>
      <h1>Gallery</h1>
      <p>{NOTE}</p>
      <div className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-6">
        {GALLERY.map((picture) => (
          <figure key={picture.caption} className="m-0">
            <img
              src={picture.file}
              alt={picture.alt}
              width="1536"
              height="864"
              className="rounded-xl shadow-sm"
            />
            <figcaption className="mt-2 text-sm text-muted-foreground">{picture.caption}</figcaption>
          </figure>
        ))}
      </div>
    </>
  );
}
