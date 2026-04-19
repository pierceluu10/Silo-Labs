"use client";

import dynamic from "next/dynamic";

export const RP2040SceneClient = dynamic(
  () => import("./RP2040Scene").then((m) => m.RP2040Scene),
  { ssr: false }
);
