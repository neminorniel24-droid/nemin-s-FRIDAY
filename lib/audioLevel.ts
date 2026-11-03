// Measures how loud YOUR voice is (0 to 1) so the orb can react to it. Nothing is recorded or sent anywhere.
/* eslint-disable @typescript-eslint/no-explicit-any */

export class MicLevel {
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private buf: Uint8Array<ArrayBuffer> | null = null;
  private smooth = 0;
  private starting = false;

  get running() {
    return !!this.analyser;
  }

  async start() {
    if (this.analyser || this.starting) return;
    this.starting = true;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      const Ctor = window.AudioContext || (window as any).webkitAudioContext;
      this.ctx = new Ctor();
      const src = this.ctx.createMediaStreamSource(this.stream);
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 256;
      this.buf = new Uint8Array(new ArrayBuffer(this.analyser.fftSize));
      src.connect(this.analyser);
    } catch {
      this.stop(); // no microphone permission: the orb just uses its built-in motion
    } finally {
      this.starting = false;
    }
  }

  stop() {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    void this.ctx?.close().catch(() => {});
    this.ctx = null;
    this.analyser = null;
    this.buf = null;
    this.smooth = 0;
  }

  /** Current loudness, smoothed. Call it every frame. */
  read = (): number => {
    if (!this.analyser || !this.buf) return 0;
    this.analyser.getByteTimeDomainData(this.buf);
    let sum = 0;
    for (let i = 0; i < this.buf.length; i++) {
      const v = (this.buf[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / this.buf.length);
    const target = Math.min(1, Math.max(0, (rms - 0.015) * 7)); // ignore the room's background hiss
    this.smooth += (target - this.smooth) * (target > this.smooth ? 0.5 : 0.12);
    return this.smooth;
  };
}
