import type { CommandAction, RoomView } from "./game-model.ru";
import type { SeatProfile } from "./table-model";
import styles from "./preferans-game.module.css";

export function SeatSwap({view, busy, profiles, command}: {
  view: RoomView; busy: boolean; profiles?: SeatProfile[] | null;
  command: (action: CommandAction, args: Record<string, unknown>) => void;
}) {
  const own = view.my_seat;
  if (own === null || !view.lobby_setup || view.status !== "lobby" || !view.occupied.every(Boolean)) return null;
  const name = (seat: number) => profiles?.[seat]?.name || `Игрок ${seat + 1}`;
  const offer = view.seat_swap;
  return <section className={styles.panel} aria-label="Перестановка мест">
    <h3>Перестановка мест</h3>
    {offer ? <>
      <p>{name(offer.from)} ↔ {name(offer.to)}. Согласий: {offer.votes.filter(Boolean).length} из 3.</p>
      <p>После согласия троих нужно снова подтвердить готовность.</p>
      <div className={styles.actions}>
        <button type="button" disabled={busy || offer.votes[own]} onClick={() => command("seat_swap_vote", {id:offer.id, approve:true})}>Согласен</button>
        <button type="button" disabled={busy} onClick={() => command("seat_swap_vote", {id:offer.id, approve:false})}>Отклонить / отменить</button>
      </div>
    </> : <div className={styles.actions}>
      {[0,1,2].filter(seat => seat !== own).map(seat => <button key={seat} type="button" disabled={busy}
        onClick={() => command("seat_swap_offer", {to:seat})}>Поменяться с {name(seat)}</button>)}
    </div>}
  </section>;
}
