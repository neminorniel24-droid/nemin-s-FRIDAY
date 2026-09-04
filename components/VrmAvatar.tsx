"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";

// A CC0-licensed VRM avatar from ToxSam's Open Source Avatars registry
// (opensourceavatars.com) — permanently hosted on Arweave, no attribution
// required. Swap this URL for any other model_file_url from
// https://raw.githubusercontent.com/ToxSam/open-source-avatars/main/data/avatars/100avatars-r1.json
// (or r2/r3) if you want a different look — same loading code handles any
// valid VRM file.
const DEFAULT_VRM_URL = "https://arweave.net/Ea1KXujzJatQgCFSMzGOzp_UtHqB1pyia--U3AtkMAY";

export type AvatarState = "idle" | "listening" | "thinking" | "speaking";

export interface VrmAvatarHandle {
  setState: (state: AvatarState) => void;
}

interface VrmAvatarProps {
  container: HTMLElement;
  vrmUrl?: string;
}

const BLINK_INTERVAL_MIN = 2500;
const BLINK_INTERVAL_MAX = 6000;
const BLINK_DURATION = 150;

// Mouth-flap "speaking" animation. This is NOT real lip-sync — the Web
// Speech API's SpeechSynthesis doesn't expose the audio waveform, so
// there's no signal to sync mouth shapes to actual phonemes. This instead
// flaps the mouth open/closed at a natural-feeling cadence for as long as
// speaking state is active, which reads as "talking" without pretending
// to be more precise than it is.
const MOUTH_FLAP_INTERVAL = 130;

export const VrmAvatar = forwardRef<VrmAvatarHandle, VrmAvatarProps>(function VrmAvatar(
  { container, vrmUrl = DEFAULT_VRM_URL },
  ref,
) {
  const stateRef = useRef<AvatarState>("idle");
  const vrmRef = useRef<VRM | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);

  useImperativeHandle(ref, () => ({
    setState: (state: AvatarState) => {
      stateRef.current = state;
    },
  }));

  useEffect(() => {
    const width = container.clientWidth;
    const height = container.clientHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 20);
    camera.position.set(0, 1.35, 1.6);
    camera.lookAt(0, 1.2, 0);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const keyLight = new THREE.DirectionalLight(0x7dfff0, 1.1);
    keyLight.position.set(1, 2, 1.5);
    scene.add(keyLight);
    const fillLight = new THREE.AmbientLight(0x14e0c0, 0.6);
    scene.add(fillLight);

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    let disposed = false;

    loader.load(
      vrmUrl,
      (gltf) => {
        if (disposed) return;
        const vrm = gltf.userData.vrm as VRM;
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        vrm.scene.rotation.y = Math.PI;
        scene.add(vrm.scene);
        vrmRef.current = vrm;
      },
      undefined,
      (error) => {
        console.error("Failed to load VRM avatar:", error);
      },
    );

    const clock = new THREE.Clock();
    let nextBlinkAt = performance.now() + BLINK_INTERVAL_MIN;
    let blinkingUntil = 0;
    let lastMouthFlap = 0;
    let mouthOpen = false;
    let animationFrame: number;

    function animate() {
      animationFrame = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const vrm = vrmRef.current;
      const now = performance.now();

      if (vrm) {
        const expressions = vrm.expressionManager;

        if (vrm.humanoid) {
          const spine = vrm.humanoid.getNormalizedBoneNode("spine");
          if (spine) spine.rotation.x = Math.sin(now / 1400) * 0.015;
        }

        if (expressions) {
          if (now >= nextBlinkAt && blinkingUntil === 0) {
            blinkingUntil = now + BLINK_DURATION;
          }
          if (blinkingUntil > 0) {
            const t = 1 - Math.abs((blinkingUntil - now) / (BLINK_DURATION / 2) - 1);
            expressions.setValue("blink", Math.max(0, Math.min(1, t)));
            if (now >= blinkingUntil) {
              blinkingUntil = 0;
              nextBlinkAt = now + BLINK_INTERVAL_MIN + Math.random() * (BLINK_INTERVAL_MAX - BLINK_INTERVAL_MIN);
              expressions.setValue("blink", 0);
            }
          }

          switch (stateRef.current) {
            case "listening":
              expressions.setValue("aa", 0);
              expressions.setValue("happy", 0.25);
              break;
            case "thinking":
              expressions.setValue("aa", 0);
              expressions.setValue("happy", 0);
              break;
            case "speaking":
              if (now - lastMouthFlap > MOUTH_FLAP_INTERVAL) {
                mouthOpen = !mouthOpen;
                lastMouthFlap = now;
              }
              expressions.setValue("aa", mouthOpen ? 0.6 : 0.05);
              break;
            default:
              expressions.setValue("aa", 0);
              expressions.setValue("happy", 0.1);
          }
        }

        if (vrm.humanoid) {
          const head = vrm.humanoid.getNormalizedBoneNode("head");
          if (head) {
            const targetTilt = stateRef.current === "thinking" ? 0.12 : 0;
            head.rotation.z += (targetTilt - head.rotation.z) * 0.06;
          }
        }

        vrm.update(delta);
      }

      renderer.render(scene, camera);
    }
    animate();

    function handleResize() {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
    window.addEventListener("resize", handleResize);

    return () => {
      disposed = true;
      cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
      vrmRef.current = null;
    };
  }, [container, vrmUrl]);

  return null;
});
