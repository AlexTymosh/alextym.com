export type Input = {
  name: string;
  label: string;
  type?: "date" | "planned-date" | "integer" | "fte" | "wte" | "boolean" | "id";
  options?: readonly string[];
  optional?: boolean;
  initial?: string;
  list?: "establishment" | "organisation" | "location" | "role" | "recruitment_source";
};

const key = (name: string, label: string, list?: Input["list"]): Input => ({ name, label, type: "id", list });
const date = (name: string, label: string): Input => ({ name, label, type: "date" });
const option = (name: string, label: string, options: readonly string[], optional = false): Input =>
  ({ name, label, options, optional });
const fte: Input = { name: "contracted_fte", label: "Contracted FTE", type: "fte", initial: "1" };
const substantive: Input = { name: "substantive", label: "Counts towards substantive WTE", type: "boolean", initial: "true" };
const line = key("line_id", "Establishment line", "establishment");
const employee = key("employee_id", "Employee ID");
const name = { name: "display_name", label: "Fictional display name (starts with Demo)" };
const vacancy = key("vacancy_id", "Vacancy ID");
const application = key("application_id", "Application ID");
const offer = key("offer_id", "Offer ID");
const occurrence = date("occurred_on", "Recorded date");
const effective = date("effective_from", "Effective from");
const positions: Input = { name: "approved_positions", label: "Positions", type: "integer", initial: "1" };

export const operationForms = {
  add_employee: { label: "Add a synthetic employee", fields: [employee, name, line, date("start_on", "Start date"), fte, substantive] },
  edit_profile: { label: "Edit display name", fields: [employee, name] },
  set_contract: { label: "Add or change a contract", fields: [employee, effective, fte, substantive,
    { name: "valid_to", label: "End date (if applicable)", type: "planned-date", optional: true }] },
  set_assignment: { label: "Transfer, promote or appoint internally", fields: [employee, effective, line,
    option("kind", "Change type", ["transfer", "promotion", "internal_appointment"])] },
  add_campaign: { label: "Create recruitment campaign", fields: [key("id", "Campaign ID"),
    { name: "label", label: "Synthetic campaign label" }, date("opened_on", "Opened on")] },
  add_vacancy: { label: "Request vacancy", fields: [vacancy, { name: "title", label: "Vacancy title" }, line,
    date("requested_on", "Requested on"), positions, { name: "approved_wte", label: "Requested WTE", type: "wte", initial: "1" },
    { ...key("campaign_id", "Campaign ID"), optional: true }] },
  move_vacancy: { label: "Approve, publish or close vacancy", fields: [vacancy, occurrence,
    option("transition", "Decision", ["approve", "publish", "close", "cancel"]),
    { name: "over_establishment_reason", label: "Over-establishment reason (approval only)", optional: true }] },
  add_application: { label: "Record an application", fields: [application, vacancy, date("received_on", "Received on"),
    key("source_code", "Recruitment source", "recruitment_source")] },
  move_application: { label: "Screen, shortlist or end an application", fields: [application, occurrence,
    option("transition", "Stage", ["screened", "shortlisted", "withdrawn", "rejected"])] },
  record_interview: { label: "Record interview outcome", fields: [application, occurrence,
    option("outcome", "Outcome", ["passed", "unsuccessful"])] },
  add_offer: { label: "Make a conditional offer", fields: [key("id", "Offer ID"), application, date("offered_on", "Offered on")] },
  decide_offer: { label: "Record offer decision", fields: [offer, date("resolved_on", "Decided on"),
    option("outcome", "Outcome", ["accepted", "declined", "withdrawn"])] },
  record_check: { label: "Record pre-employment checks", fields: [offer, date("checked_on", "Checked on"),
    option("status", "Status", ["pending", "passed", "failed"])] },
  confirm_start: { label: "Confirm planned start", fields: [application, occurrence,
    { name: "planned_start_on", label: "Planned start date", type: "planned-date" }] },
  record_starter: { label: "Record an actual start", fields: [offer, date("started_on", "Actual start date"), fte] },
  record_probation: { label: "Record probation outcome", fields: [employee, occurrence,
    option("outcome", "Probation outcome", ["passed", "extended", "unsuccessful"])] },
  record_learning: { label: "Record learning", fields: [key("id", "Learning event ID"), employee, occurrence,
    key("activity_code", "Activity code"), { name: "completed", label: "Completed", type: "boolean", initial: "true" }] },
  record_pdr: { label: "Record PDR", fields: [key("id", "PDR event ID"), employee, occurrence,
    option("status", "Status", ["due", "completed", "overdue"])] },
  record_leaver: { label: "Record a leaver", fields: [employee, date("leaving_date", "First inactive date"),
    option("reason", "Leaving reason", ["resignation", "retirement", "fixed_term_end", "other"])] },
  set_reference: { label: "Add or edit a reference value", fields: [
    option("kind", "Reference type", ["organisation", "location", "role", "recruitment_source"]),
    key("id", "Reference code"), { name: "label", label: "Synthetic label" },
    { name: "active", label: "Available for new records", type: "boolean", initial: "true" },
    option("pay_band", "Pay band (roles only)", ["2", "3", "4", "5", "6", "7", "8a", "8b", "Not specified"], true)] },
  add_establishment_line: { label: "Create an establishment line", fields: [
    key("id", "Establishment ID"), key("organisation_id", "Service area", "organisation"),
    key("location_id", "Location", "location"), key("role_id", "Role", "role"),
    effective, positions, { name: "budgeted_wte", label: "Budgeted WTE", type: "wte", initial: "1" }] },
} satisfies Record<string, { label: string; fields: Input[] }>;

export type Action = keyof typeof operationForms;
