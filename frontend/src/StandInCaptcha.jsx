import { useState } from "react";

// Stand-in for a real CAPTCHA (spec F01, U7). It protects nothing: ticking it
// simply produces a fixed token. A real provider replaces it in a later feature.
export default function StandInCaptcha({ onToken }) {
  const [ticked, setTicked] = useState(false);

  function handleChange(event) {
    setTicked(event.target.checked);
    onToken(event.target.checked ? "stand-in-token" : "");
  }

  return (
    <div>
      <input id="captcha" type="checkbox" checked={ticked} onChange={handleChange} />
      <label htmlFor="captcha">I am not a robot</label>
    </div>
  );
}
