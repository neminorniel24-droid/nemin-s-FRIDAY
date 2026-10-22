// Grabs one picture from the camera or the screen, shrunk and compressed for the AI.

function frameToDataUrl(video: HTMLVideoElement, maxW = 1024): string {
  const scale = Math.min(1, maxW / (video.videoWidth || maxW));
  const c = document.createElement("canvas");
  c.width = Math.round((video.videoWidth || 640) * scale);
  c.height = Math.round((video.videoHeight || 480) * scale);
  c.getContext("2d")!.drawImage(video, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.75);
}

async function grab(stream: MediaStream, maxW: number): Promise<string> {
  const v = document.createElement("video");
  v.muted = true;
  v.playsInline = true;
  v.srcObject = stream;
  await v.play();
  await new Promise((r) => setTimeout(r, 500)); // let the exposure settle
  const url = frameToDataUrl(v, maxW);
  stream.getTracks().forEach((t) => t.stop());
  return url;
}

/** If the hand-gesture camera is already running, reuse its picture. */
export async function captureCamera(existing?: HTMLVideoElement | null): Promise<string> {
  if (existing && existing.readyState >= 2 && existing.videoWidth > 0) return frameToDataUrl(existing);
  return grab(await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } }), 1024);
}

export async function captureScreen(): Promise<string> {
  const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
  return grab(stream, 1600);
}
