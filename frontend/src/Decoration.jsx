// A picture used as decoration: a screen reader passes over it
// (docs/specs/public-pages.md, I3).
export default function Decoration({ picture }) {
  return <img src={picture.file} alt="" width="1536" height="864" />;
}
