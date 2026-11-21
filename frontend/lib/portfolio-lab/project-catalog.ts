import manifests from "../../.generated/portfolio-projects.json";

export type LabProject = {
  id: string;
  title: string;
  summary: string;
  path: string;
  category: string;
  technologies: readonly string[];
  catalogVisible: boolean;
};

export const labProjects: readonly LabProject[] = manifests;
export const publicProjects = labProjects.filter((project) => project.catalogVisible);
