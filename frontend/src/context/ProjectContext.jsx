import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const ProjectContext = createContext(null);

export function ProjectProvider({ children }) {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(() => localStorage.getItem("projectId") || null);

  useEffect(() => {
    api.get("/projects").then(({ data }) => {
      setProjects(data);
      setProjectId((prev) => {
        const valid = data.find((p) => p.id === prev);
        return valid ? prev : (data[0]?.id || null);
      });
    });
  }, []);

  useEffect(() => {
    if (projectId) localStorage.setItem("projectId", projectId);
  }, [projectId]);

  const project = projects.find((p) => p.id === projectId);

  return (
    <ProjectContext.Provider value={{ projects, project, projectId, setProjectId }}>
      {children}
    </ProjectContext.Provider>
  );
}

export const useProject = () => useContext(ProjectContext);
