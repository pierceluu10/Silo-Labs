import { WorkspaceLayout } from "@/components/workspace/WorkspaceLayout";

interface Props {
  searchParams: Promise<{ prompt?: string }>;
}

export default async function WorkspacePage({ searchParams }: Props) {
  const { prompt } = await searchParams;
  const effective =
    prompt?.trim() || "BME280 over I2C → SSD1306 OLED";
  return <WorkspaceLayout prompt={effective} />;
}
