import type { RoomView, CommandAction } from "./game-model.ru";
import styles from "./preferans-game.module.css";

const label = (seat: number) => `Игрок ${seat + 1}`;

export function SheetExit({ view, busy, command }: {
  view: RoomView; busy: boolean;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
}) {
  const seat = view.my_seat;
  if (seat === null || !["playing", "between", "awaiting_settlement"].includes(view.status) || !view.game_id || !view.occupied.every(Boolean)) return null;
  const offers = view.sheet_offers ?? [];
  const incoming = offers.find(offer => offer.to === seat);
  const confirm = () => window.confirm("Завершить всю партию? Ты получишь техническое поражение и два условных голых удара; оба соперника — первое место. Незакрытая пуля не рассчитывается. Действие необратимо.");
  return <details className={styles.adjustments} open={incoming ? true : undefined}>
    <summary>Выбросить листик{incoming ? " — есть предложение" : ""}</summary>
    <p>Только добровольное решение игрока. Предложение можно отклонить без штрафа. Удары — исключительно шуточные записи.</p>
    {incoming && <div className={styles.controlNote} role="group" aria-label="Предложение выбросить листик">
      <strong>{label(incoming.from)} предлагает тебе завершить партию.</strong>
      <div className={styles.actions}>
        <button type="button" disabled={busy} onClick={() => { if (confirm()) command("sheet_reply", { offer_id: incoming.id, accept: true }); }}>Принять предложение</button>
        <button type="button" disabled={busy} onClick={() => command("sheet_reply", { offer_id: incoming.id, accept: false })}>Отказаться</button>
      </div>
    </div>}
    <div className={styles.actions}>
      <button type="button" disabled={busy} onClick={() => { if (confirm()) command("sheet_discard", { confirm: true }); }}>Выбросить листик самому</button>
      {[0, 1, 2].filter(target => target !== seat).map(target => <button type="button" key={target}
        disabled={busy || offers.some(offer => offer.to === target)}
        onClick={() => command("sheet_offer", { target })}>Предложить: {label(target)}</button>)}
    </div>
    {offers.filter(offer => offer.from === seat).map(offer => <p key={offer.id} role="status">Ожидаем решения: {label(offer.to)}. Предложение действует до следующей раздачи.</p>)}
  </details>;
}
