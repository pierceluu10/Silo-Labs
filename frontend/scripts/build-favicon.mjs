import sharp from "sharp";
import path from "node:path";

const PUBLIC_DIR = path.resolve("public");
const SRC = path.join(PUBLIC_DIR, "silolabslogo.png");

const TILE_BG = { r: 5, g: 5, b: 7, alpha: 1 }; // matches --color-abyss
const WHITE_THRESHOLD = 235; // pixels brighter than this become transparent

/** Convert near-white pixels in the source to alpha=0, then trim, so we get the bare mark. */
async function loadCleanedMark() {
  const { data, info } = await sharp(SRC)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const { width, height, channels } = info;
  // Walk RGBA; near-white → alpha 0.
  for (let i = 0; i < data.length; i += channels) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    if (r >= WHITE_THRESHOLD && g >= WHITE_THRESHOLD && b >= WHITE_THRESHOLD) {
      data[i + 3] = 0;
    }
  }

  // Repack to PNG, then trim transparent edges so resize fills the tile.
  const png = await sharp(data, { raw: { width, height, channels } })
    .png()
    .toBuffer();
  return sharp(png).trim().png().toBuffer();
}

async function buildTile(size, radius, padPct, outName) {
  const cleaned = await loadCleanedMark();
  const inner = Math.round(size * (1 - padPct * 2));
  const fitted = await sharp(cleaned)
    .resize(inner, inner, {
      fit: "contain",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer();

  const mask = Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
      <rect x="0" y="0" width="${size}" height="${size}" rx="${radius}" ry="${radius}" fill="white"/>
    </svg>`,
  );

  await sharp({
    create: { width: size, height: size, channels: 4, background: TILE_BG },
  })
    .composite([
      { input: fitted, gravity: "center" },
      { input: mask, blend: "dest-in" },
    ])
    .png()
    .toFile(path.join(PUBLIC_DIR, outName));

  console.log(`wrote public/${outName} (${size}x${size}, r=${radius})`);
}

/** Save a transparent-bg version of the cleaned mark for in-page use. */
async function buildTransparentMark(outName, maxSize = 512) {
  const cleaned = await loadCleanedMark();
  await sharp(cleaned)
    .resize(maxSize, maxSize, {
      fit: "inside",
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toFile(path.join(PUBLIC_DIR, outName));
  console.log(`wrote public/${outName} (transparent, max ${maxSize}px)`);
}

await Promise.all([
  buildTile(64, 14, 0.1, "favicon-64.png"),
  buildTile(32, 7, 0.08, "favicon-32.png"),
  buildTile(180, 38, 0.1, "apple-icon.png"),
  buildTransparentMark("silo-mark.png", 256),
]);
