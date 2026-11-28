import {createTranslator,type MessageKey} from "../i18n/messages";
export const t = createTranslator("ru");
export function name(id:string) { return t(`decor.${id}` as MessageKey); }
