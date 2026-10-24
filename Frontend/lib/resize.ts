/** CLIP은 어차피 224px로 줄여서 보고, 512px에서도 점수·제거 판정이 원본과 같았다(이슈 #22 실측) */
export const RESIZE_LONG_SIDE = 512;
export const JPEG_QUALITY = 0.85;

export function fitWithin(width: number, height: number, maxSide: number): { width: number; height: number } {
  const longSide = Math.max(width, height);
  if (longSide <= maxSide) return { width, height };
  const scale = maxSide / longSide;
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

/** 휴대폰 사진을 긴 변 512px JPEG로 줄인다. EXIF 회전 정보를 반영해 세로 사진이 눕지 않게 한다 */
export async function resizeImage(file: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    const { width, height } = fitWithin(bitmap.width, bitmap.height, RESIZE_LONG_SIDE);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("canvas 2d 컨텍스트를 만들 수 없음");
    context.drawImage(bitmap, 0, 0, width, height);
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("JPEG 변환 실패"))), "image/jpeg", JPEG_QUALITY);
    });
  } finally {
    bitmap.close();
  }
}
