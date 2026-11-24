import { cardArtwork, cardBackArtwork } from "./atlas-art";
import { cardLabel, type Card } from "./game-model.ru";
import { isCard } from "./table-model";
import styles from "./preferans-table.module.css";

export function CardArtwork({ card, decorative = false }: { card?: Card; decorative?: boolean }) {
  // Invalid face data is never interpreted as an asset URL.
  const face = card && isCard(card) ? card : undefined;
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={styles.artwork} src={face ? cardArtwork(face) : cardBackArtwork}
    alt={decorative ? "" : face ? cardLabel(face) : "Закрытая карта"} aria-hidden={decorative || undefined}
    draggable={false} width={100} height={146} />;
}
