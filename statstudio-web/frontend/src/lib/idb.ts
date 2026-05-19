// IndexedDB persistence layer using the `idb` micro-lib.
import { openDB, IDBPDatabase } from "idb";
import type { ProjectFile } from "./types";

const DB_NAME = "statstudio";
const DB_VERSION = 1;

interface SavedProject {
  name: string;
  updated_at: string;
  project: ProjectFile;
}

let dbPromise: Promise<IDBPDatabase> | null = null;

function db() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(d) {
        if (!d.objectStoreNames.contains("projects")) {
          d.createObjectStore("projects", { keyPath: "name" });
        }
        if (!d.objectStoreNames.contains("kv")) {
          d.createObjectStore("kv");
        }
      },
    });
  }
  return dbPromise;
}

export const idb = {
  async saveProject(project: ProjectFile) {
    const d = await db();
    const record: SavedProject = {
      name: project.name,
      updated_at: new Date().toISOString(),
      project,
    };
    await d.put("projects", record);
  },
  async listProjects(): Promise<SavedProject[]> {
    try {
      const d = await db();
      return (await d.getAll("projects")) as SavedProject[];
    } catch {
      return [];
    }
  },
  async loadProject(name: string): Promise<ProjectFile | null> {
    const d = await db();
    const rec = (await d.get("projects", name)) as SavedProject | undefined;
    return rec?.project ?? null;
  },
  async deleteProject(name: string) {
    const d = await db();
    await d.delete("projects", name);
  },
  async kvSet(key: string, value: any) {
    const d = await db();
    await d.put("kv", value, key);
  },
  async kvGet<T = any>(key: string): Promise<T | null> {
    try {
      const d = await db();
      return ((await d.get("kv", key)) as T) ?? null;
    } catch {
      return null;
    }
  },
};
