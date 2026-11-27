/** Read-only final award geometry; no scoring or game mutations. */
export type NotebookPunch = {from:number;to:number;bare:number;ordinary:number};
type Position = "left" | "right" | "bottom";
type Seats = Record<Position,number>;
type Point = {x:number;y:number};
const isSeat=(n:unknown):n is number=>n===0||n===1||n===2;
const count=(n:unknown):n is number=>typeof n==="number"&&Number.isSafeInteger(n)&&n>=0;

export function isNotebookPunches(value:unknown,net:readonly number[]):value is NotebookPunch[] {
  if(!Array.isArray(value)||value.length>3)return false;
  const seen=new Set<string>();
  for(const item of value){
    if(!item||typeof item!=="object")return false;
    const {from,to,bare,ordinary}=item;
    if(!isSeat(from)||!isSeat(to)||from===to||!count(bare)||!count(ordinary)||(!bare&&!ordinary)||!(net[from]>net[to]))return false;
    const key=`${Math.min(from,to)}:${Math.max(from,to)}`;
    if(seen.has(key))return false;
    seen.add(key);
  }
  return true;
}

/** Arrow direction follows seats, not the sign of the individual pair balance. */
export function punchGeometry(punch:NotebookPunch,seats:Seats,w:number,cy:number,inner:number,innerY:number):{center:Point;start:Point;end:Point} {
  const position=(seat:number):Position=>seat===seats.left?"left":seat===seats.right?"right":"bottom";
  const from=position(punch.from),to=position(punch.to);
  const cx=w/2, reach=63;
  if(from!=="bottom"&&to!=="bottom"){
    const center={x:cx,y:49};
    const left={x:cx-reach,y:center.y},right={x:cx+reach,y:center.y};
    return {center,start:from==="left"?left:right,end:to==="left"?left:right};
  }
  const side=from==="bottom"?to:from;
  const sign=side==="left"?-1:1;
  const ax=cx+sign*43, ay=cy+21;
  const bx=side==="left"?inner:w-inner;
  const dx=bx-ax,dy=innerY-ay,len=Math.hypot(dx,dy);
  const center={x:ax+dx*.531,y:ay+dy*.531};
  // Outward normal points into the side player's sector.
  const nx=sign*dy/len,ny=-sign*dx/len;
  const outside={x:center.x+reach*nx,y:center.y+reach*ny};
  const inside={x:center.x-reach*nx,y:center.y-reach*ny};
  return {center,start:from==="bottom"?inside:outside,end:to==="bottom"?inside:outside};
}
