import { WorkspaceLayout } from "@/components/workspace/WorkspaceLayout";
import { DEFAULT_MCU } from "@/lib/mcus";
import { WORKSPACE_PROMPT } from "@/lib/prompts";

interface Props {
  searchParams: Promise<{ prompt?: string; mcu?: string }>;
}

export default async function WorkspacePage({ searchParams }: Props) {
  const { prompt, mcu } = await searchParams;
  return <WorkspaceLayout prompt={prompt?.trim() || WORKSPACE_PROMPT} mcu={mcu || DEFAULT_MCU} />;
}
