import manifests from "../../.generated/portfolio-projects.json";

export const labProjects: ReadonlyArray<{ id: string; title: string; summary: string; path: string }> = manifests;
