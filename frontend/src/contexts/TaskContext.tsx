import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { pollTaskUntilDone } from '@/api/client';
import { useTranslation } from 'react-i18next';

export type TaskType = 'evaluation' | 'objection';

export interface PendingTask {
  taskId: string;
  type: TaskType;
  isFinal?: boolean;
  evalId?: number;
  status: 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED';
  errorMessage?: string;
}

interface ToastInfo {
  message: string;
  type: 'success' | 'error';
}

interface TaskContextType {
  pendingTasks: PendingTask[];
  isUploading: boolean;
  setIsUploading: (val: boolean) => void;
  startTask: (task: Omit<PendingTask, 'status'>) => void;
  dismissTask: (taskId: string) => void;
  toast: ToastInfo | null;
  clearToast: () => void;
  showToastNotification: (message: string, type: 'success' | 'error') => void;
  getTaskByType: (type: TaskType) => PendingTask | undefined;
}

const TaskContext = createContext<TaskContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY = 'judgie_pending_tasks';

export const TaskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [pendingTasks, setPendingTasks] = useState<PendingTask[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [toast, setToast] = useState<ToastInfo | null>(null);
  const { t } = useTranslation();

  const clearToast = useCallback(() => setToast(null), []);

  const showToastNotification = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type });
  }, []);

  const dismissTask = useCallback((taskId: string) => {
    setPendingTasks((prev) => {
      const updated = prev.filter((t) => t.taskId !== taskId);
      // Update localStorage (only active tasks)
      const activeTasks = updated.filter((t) => t.status === 'PENDING' || t.status === 'PROCESSING');
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(activeTasks));
      return updated;
    });
  }, []);

  const getTaskByType = useCallback((type: TaskType) => {
    return pendingTasks.find((t) => t.type === type);
  }, [pendingTasks]);

  // helper to save active tasks to localStorage
  const saveToLocalStorage = (tasks: PendingTask[]) => {
    const activeTasks = tasks.filter((t) => t.status === 'PENDING' || t.status === 'PROCESSING');
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(activeTasks));
  };

  const pollTask = useCallback(async (task: Omit<PendingTask, 'status'>) => {
    // Add task to pending list if not already there
    setPendingTasks((prev) => {
      const exists = prev.some((t) => t.taskId === task.taskId);
      if (exists) return prev;
      const updated = [...prev, { ...task, status: 'PENDING' as const }];
      saveToLocalStorage(updated);
      return updated;
    });

    try {
      const result = await pollTaskUntilDone(
        task.taskId,
        (updatedTask) => {
          // Update status in local memory and localStorage
          setPendingTasks((prev) => {
            const updated = prev.map((t) =>
              t.taskId === task.taskId ? { ...t, status: updatedTask.status } : t
            );
            saveToLocalStorage(updated);
            return updated;
          });
        }
      );

      if (result.status === 'SUCCESS') {
        setPendingTasks((prev) => {
          const updated = prev.map((t) =>
            t.taskId === task.taskId ? { ...t, status: 'SUCCESS' as const } : t
          );
          saveToLocalStorage(updated); // This removes it from localStorage via filter
          return updated;
        });

        const msg = task.type === 'evaluation' 
          ? t('toast.eval_success') 
          : t('toast.objection_success');
        showToastNotification(msg, 'success');
      } else {
        const errorMsg = result.error_message || 'Unknown error occurred.';
        setPendingTasks((prev) => {
          const updated = prev.map((t) =>
            t.taskId === task.taskId 
              ? { ...t, status: 'FAILED' as const, errorMessage: errorMsg } 
              : t
          );
          saveToLocalStorage(updated);
          return updated;
        });

        const msg = task.type === 'evaluation'
          ? t('toast.eval_failed', { error: errorMsg })
          : t('toast.objection_failed', { error: errorMsg });
        showToastNotification(msg, 'error');
      }
    } catch (err: any) {
      const errorMsg = err.message || 'Network error.';
      setPendingTasks((prev) => {
        const updated = prev.map((t) =>
          t.taskId === task.taskId 
            ? { ...t, status: 'FAILED' as const, errorMessage: errorMsg } 
            : t
        );
        saveToLocalStorage(updated);
        return updated;
      });

      const msg = task.type === 'evaluation'
        ? t('toast.eval_failed', { error: errorMsg })
        : t('toast.objection_failed', { error: errorMsg });
      showToastNotification(msg, 'error');
    }
  }, [t, showToastNotification]);

  const startTask = useCallback((task: Omit<PendingTask, 'status'>) => {
    pollTask(task);
  }, [pollTask]);

  // Load from localStorage on mount and start polling
  useEffect(() => {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (raw) {
      try {
        const saved = JSON.parse(raw) as Omit<PendingTask, 'status'>[];
        saved.forEach((task) => {
          pollTask(task);
        });
      } catch (e) {
        console.error('Failed to restore pending tasks from localStorage:', e);
        localStorage.removeItem(LOCAL_STORAGE_KEY);
      }
    }
  }, [pollTask]);

  return (
    <TaskContext.Provider
      value={{
        pendingTasks,
        isUploading,
        setIsUploading,
        startTask,
        dismissTask,
        toast,
        clearToast,
        showToastNotification,
        getTaskByType,
      }}
    >
      {children}
    </TaskContext.Provider>
  );
};

export const useTask = () => {
  const context = useContext(TaskContext);
  if (!context) {
    throw new Error('useTask must be used within a TaskProvider');
  }
  return context;
};
