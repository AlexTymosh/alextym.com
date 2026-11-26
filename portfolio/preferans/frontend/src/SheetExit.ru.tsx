import type { RoomView, CommandAction } from "./game-model.ru";

export function SheetExit({ view, busy, command }: {
  view: RoomView; busy: boolean;
  command: (action: CommandAction, args?: Record<string, unknown>) => void;
}) {
  if (view.my_seat === null || !["playing", "between", "awaiting_settlement"].includes(view.status) || !view.game_id || !view.occupied.every(Boolean)) return null;
  return <button type="button" disabled={busy} onClick={()=>{
    if(window.confirm("Порвать листик и закончить партию? Ты получишь техническое поражение и два условных голых удара; оба соперника — первое место. Незакрытая пуля не рассчитывается. Действие необратимо."))command("sheet_discard",{confirm:true});
  }}>Порвать листик и выкинуть</button>;
}
