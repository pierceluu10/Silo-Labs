import { HeroText } from "@/components/landing/HeroText";
import { PromptDemo } from "@/components/landing/PromptDemo";
import { RP2040SceneClient } from "@/components/landing/RP2040SceneClient";

export default function LandingPage() {
  return (
    <main className="min-h-screen grid grid-cols-1 lg:grid-cols-2 gap-8 px-6 py-16 items-center">
      <HeroText />
      {/* Right column: chip on top, typing strip beneath, both centered to the column */}
      <div className="flex h-[520px] min-h-0 flex-col items-center justify-center lg:h-[600px]">
        <div className="relative w-full min-h-0 flex-1 translate-x-2 -translate-y-2 sm:translate-x-3 lg:translate-x-4">
          <RP2040SceneClient />
        </div>
        <div className="-mt-6 flex w-full justify-center sm:-mt-10 lg:-mt-14">
          <PromptDemo />
        </div>
      </div>
    </main>
  );
}
