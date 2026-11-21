"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import authStyles from "./lab-auth.module.css";
import styles from "./settings.module.css";

const clamp = (value: number) => Math.min(100, Math.max(0, value));

export function AvatarCropper({ source, onApply, onCancel }: {
  source: string; onApply: (image: string) => void; onCancel: () => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ x: number; y: number; horizontal: number; vertical: number } | null>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [horizontal, setHorizontal] = useState(50);
  const [vertical, setVertical] = useState(50);
  const [fit, setFit] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const loaded = new Image();
    loaded.onload = () => {
      if (!active) return;
      if (!loaded.naturalWidth || loaded.naturalWidth * loaded.naturalHeight > 16_000_000) {
        setError("Choose an image up to 16 megapixels.");
      } else setImage(loaded);
    };
    loaded.onerror = () => { if (active) setError("This image could not be opened. Choose another photo."); };
    loaded.src = source;
    return () => { active = false; loaded.onload = null; loaded.onerror = null; };
  }, [source]);

  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!image || !context || !canvas.current) return;
    const size = canvas.current.width;
    const width = image.naturalWidth;
    const height = image.naturalHeight;
    context.clearRect(0, 0, size, size);
    if (fit) {
      // The complete rectangle fits inside the circular avatar without distortion.
      const scale = size / Math.hypot(width, height);
      context.drawImage(image, (size - width * scale) / 2, (size - height * scale) / 2, width * scale, height * scale);
    } else {
      const side = Math.min(width, height) / zoom;
      context.drawImage(image, (width - side) * horizontal / 100,
        (height - side) * vertical / 100, side, side, 0, 0, size, size);
    }
  }, [image, zoom, horizontal, vertical, fit]);

  function move(event: PointerEvent<HTMLCanvasElement>) {
    if (!drag.current || !image || fit) return;
    const side = Math.min(image.naturalWidth, image.naturalHeight) / zoom;
    const scale = side / event.currentTarget.getBoundingClientRect().width;
    const width = image.naturalWidth - side;
    const height = image.naturalHeight - side;
    if (width > 0) setHorizontal(clamp(drag.current.horizontal - (event.clientX - drag.current.x) * scale / width * 100));
    if (height > 0) setVertical(clamp(drag.current.vertical - (event.clientY - drag.current.y) * scale / height * 100));
  }

  return <section className={styles.cropper} aria-labelledby="avatar-editor-title">
    <div><h3 id="avatar-editor-title">Adjust your photo</h3>
      <p className={authStyles.hint}>Keep the original proportions. Drag the photo or use the controls to frame your avatar.</p>
    </div>
    <canvas ref={canvas} width={320} height={320} role="img" aria-label="Avatar crop preview"
      className={styles.cropPreview} onPointerDown={(event) => {
        if (event.button !== 0 || fit || !image) return;
        drag.current = { x: event.clientX, y: event.clientY, horizontal, vertical };
        event.currentTarget.setPointerCapture(event.pointerId);
      }} onPointerMove={move} onPointerUp={() => { drag.current = null; }}
      onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }} />
    <div className={styles.photoChoices} role="group" aria-label="Photo framing">
      <button type="button" className={authStyles.secondaryButton} aria-pressed={!fit} onClick={() => setFit(false)}>Crop photo</button>
      <button type="button" className={authStyles.secondaryButton} aria-pressed={fit} onClick={() => setFit(true)}>Fit whole photo</button>
    </div>
    <div className={styles.cropControls}>
      <label>Zoom <span>{zoom.toFixed(2)}×</span>
        <input type="range" aria-label="Photo zoom" min={1} max={4} step={0.01} value={zoom}
          disabled={fit || !image} onChange={(event) => setZoom(Number(event.target.value))} />
      </label>
      <label>Horizontal position
        <input type="range" aria-label="Horizontal position" min={0} max={100} value={horizontal}
          disabled={fit || !image} onChange={(event) => setHorizontal(Number(event.target.value))} />
      </label>
      <label>Vertical position
        <input type="range" aria-label="Vertical position" min={0} max={100} value={vertical}
          disabled={fit || !image} onChange={(event) => setVertical(Number(event.target.value))} />
      </label>
    </div>
    {error && <p role="alert">{error}</p>}
    <div className={styles.photoChoices}>
      <button type="button" className={authStyles.primaryButton} disabled={!image || Boolean(error)}
        onClick={() => {
          try { if (canvas.current) onApply(canvas.current.toDataURL("image/png")); }
          catch { setError("Could not prepare this photo. Choose another image."); }
        }}>Use photo</button>
      <button type="button" className={authStyles.secondaryButton} onClick={onCancel}>Cancel crop</button>
    </div>
  </section>;
}
