// Logical presentation only; no game seat is allocated here.
const fixed: Record<number, string[]> = {1:["5 / 3"],2:["5 / 1","1 / 5"],3:["5 / 3","1 / 1","1 / 5"],4:["5 / 3","3 / 1","1 / 3","3 / 5"]};
const perimeter = ["5 / 3","5 / 1","3 / 1","1 / 1","1 / 2","1 / 3","1 / 4","1 / 5","3 / 5","5 / 5"];
export function positions(count:number):string[] {
  if (!Number.isInteger(count) || count<0 || count>10) throw new RangeError("Invalid participant count");
  return [...(fixed[count]??perimeter.slice(0,count))];
}
