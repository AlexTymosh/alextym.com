/** Pure display layout. All scoring values are supplied by the server. */
export type InkToken = { label:string; manual?:boolean; latest?:boolean; underline?:boolean };
export const tokenWidth = (token:InkToken):number => token.label.length*9.5+(token.manual?112:0)+7;

export function packNotebookRows(tokens:readonly InkToken[], maxWidth:number):InkToken[][] {
  if(!Number.isFinite(maxWidth)||maxWidth<=0)throw new Error("Positive row width required");
  const rows:InkToken[][]=[];
  let row:InkToken[]=[], width=0;
  for(const token of tokens){
    const size=tokenWidth(token);
    if(row.length&&width+size>maxWidth){rows.push(row);row=[];width=0;}
    row.push(token);width+=size;
  }
  if(row.length)rows.push(row);
  return rows;
}

export function poolEntryText(values:readonly number[],index:number,target:number):string {
  const value=values[index];
  return value===target&&(index===0||values[index-1]!==target)?`<<${value}>>`:String(value);
}

/** Distributed hill is never posted again: this is the final display calculation. */
export function vistEquation(before:number,distributed:number):InkToken[] {
  return [{label:`${before} +`},{label:String(distributed),underline:true},{label:`= ${before+distributed}`}];
}
