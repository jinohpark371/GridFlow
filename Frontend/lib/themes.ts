export type ThemeId = "mono" | "vivid" | "golden";

export interface Theme {
  id: ThemeId;
  label: string;
  description: string;
  /** 서버에 보내는 영어 문장 — ScoringMLP 학습 테마(Ai/collect_unsplash_data.py의 THEMES)와 정확히 같아야 함 */
  prompt: string;
  /** 테마 카드에 보여줄 예시 색 3개 */
  swatch: readonly [string, string, string];
}

export const THEMES: readonly Theme[] = [
  {
    id: "mono",
    label: "흑백",
    description: "색을 덜어내고 빛과 그림자로",
    prompt: "black and white monochrome photography",
    swatch: ["#111111", "#7a7a7a", "#e6e6e6"],
  },
  {
    id: "vivid",
    label: "비비드",
    description: "선명하고 다채로운 색감",
    prompt: "vibrant colorful photography",
    swatch: ["#ff3b6b", "#ffc93c", "#2ec4b6"],
  },
  {
    id: "golden",
    label: "골든아워",
    description: "해 질 녘의 따뜻한 빛",
    prompt: "warm golden hour sunset photography",
    swatch: ["#ff8a3d", "#f6c26b", "#7a3e2b"],
  },
];

export function getTheme(id: ThemeId): Theme {
  const theme = THEMES.find((t) => t.id === id);
  if (!theme) throw new Error(`알 수 없는 테마: ${id}`);
  return theme;
}
