export type RuleQuestion = { title: string; body: string };
export type RuleTopic = { title: string; intro: string; questions: RuleQuestion[] };

/** Parse the project's Markdown heading hierarchy, preserving every answer. */
export function ruleTopics(source: string): RuleTopic[] {
  const result: RuleTopic[] = [];
  let topic: RuleTopic | undefined;
  let question: RuleQuestion | undefined;
  for (const line of source.split(/\r?\n/)) {
    if (line.startsWith("## ")) {
      topic = {title:line.slice(3),intro:"",questions:[]};
      question=undefined;
      result.push(topic);
    } else if (line.startsWith("### ") && topic) {
      question={title:line.slice(4),body:""};
      topic.questions.push(question);
    } else if (question) question.body+=line+"\n";
    else if (topic) topic.intro+=line+"\n";
  }
  return result;
}
