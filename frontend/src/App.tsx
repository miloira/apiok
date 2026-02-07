import { useState, useEffect, useRef } from 'react';
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import json from 'react-syntax-highlighter/dist/esm/languages/hljs/json';
import xml from 'react-syntax-highlighter/dist/esm/languages/hljs/xml';
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript';
import css from 'react-syntax-highlighter/dist/esm/languages/hljs/css';
import { githubGist } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import { api } from './api/client';
import type { Request, Environment, ExecuteResponse, HttpMethod, History, Folder, DragData, DropTarget, DragItemType } from './types';
import { calcGapPosition, reorderList } from './utils/dragUtils';
import './App.css';

SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('xml', xml);
SyntaxHighlighter.registerLanguage('html', xml);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('css', css);

const HTTP_METHODS: HttpMethod[] = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'];

const METHOD_COLORS: Record<HttpMethod, string> = {
  GET: '#61affe',
  POST: '#49cc90',
  PUT: '#fca130',
  DELETE: '#f93e3e',
  PATCH: '#50e3c2',
  HEAD: '#9012fe',
  OPTIONS: '#0d5aa7',
};

type Theme = 'purple' | 'blue' | 'green' | 'orange' | 'pink' | 'dark' | 'silver';

const THEMES: { id: Theme; name: string; color: string }[] = [
  { id: 'purple', name: '紫色', color: '#8b5cf6' },
  { id: 'blue', name: '蓝色', color: '#3b82f6' },
  { id: 'green', name: '绿色', color: '#10b981' },
  { id: 'orange', name: '橙色', color: '#f97316' },
  { id: 'pink', name: '粉色', color: '#ec4899' },
  { id: 'dark', name: '暗色', color: '#6366f1' },
  { id: 'silver', name: '银色', color: '#94a3b8' },
];

const Icon = ({ d, size = 14, color = 'currentColor' }: { d: string; size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

const Icons = {
  rocket: (s = 14) => <Icon d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09zM12 15l-3-3M22 2l-7.5 7.5" size={s} />,
  folder: (s = 14) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>,
  plus: (s = 14) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  copy: (s = 14) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>,
  edit: (s = 14) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  trash: (s = 14) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>,
  warning: (s = 14) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  palette: (s = 14) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="13.5" cy="6.5" r="0.5" fill="currentColor"/><circle cx="17.5" cy="10.5" r="0.5" fill="currentColor"/><circle cx="8.5" cy="7.5" r="0.5" fill="currentColor"/><circle cx="6.5" cy="12.5" r="0.5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>,
};

interface ContextMenu {
  x: number;
  y: number;
  type: 'background' | 'request' | 'folder';
  targetId?: number;
  parentFolderId?: number;
}

interface ParamItem {
  key: string;
  value: string;
  description: string;
  enabled: boolean;
}

interface RequestTab {
  id: string;
  requestId?: number;
  name: string;
  method: HttpMethod;
  url: string;
  headers: ParamItem[];
  queryParams: ParamItem[];
  body: string;
  folder_id?: number;
  response: ExecuteResponse | null;
  dirty: boolean;
}

const emptyParam = (): ParamItem => ({ key: '', value: '', description: '', enabled: true });

function App() {
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem('theme') as Theme) || 'purple');
  const [folders, setFolders] = useState<Folder[]>([]);
  const [standaloneRequests, setStandaloneRequests] = useState<Request[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [activeTab, setActiveTab] = useState<'requests' | 'history' | 'environments'>('requests');
  const [expandedFolders, setExpandedFolders] = useState<Set<number>>(new Set());
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);

  // Unified drag state
  const [dragData, setDragData] = useState<DragData | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);

  const tabCounter = useRef(1);
  const makeTabId = () => `tab-${tabCounter.current++}`;

  const [openTabs, setOpenTabs] = useState<RequestTab[]>([{
    id: 'tab-0', name: '新建请求', method: 'GET', url: '',
    headers: [emptyParam()], queryParams: [emptyParam()],
    body: '', response: null, dirty: true,
  }]);
  const [activeTabId, setActiveTabId] = useState('tab-0');

  const currentTab = openTabs.find(t => t.id === activeTabId) || openTabs[0];
  const currentRequest = {
    id: currentTab?.requestId,
    name: currentTab?.name || '',
    method: currentTab?.method || 'GET' as HttpMethod,
    url: currentTab?.url || '',
    headers: currentTab?.headers || [emptyParam()],
    queryParams: currentTab?.queryParams || [emptyParam()],
    body: currentTab?.body || '',
    folder_id: currentTab?.folder_id,
  };
  const response = currentTab?.response || null;

  const setCurrentRequest = (req: typeof currentRequest) => {
    setOpenTabs(tabs => tabs.map(t => t.id === activeTabId ? {
      ...t, requestId: req.id, name: req.name, method: req.method, url: req.url,
      headers: req.headers, queryParams: req.queryParams, body: req.body,
      folder_id: req.folder_id, dirty: true,
    } : t));
  };

  const setResponse = (resp: ExecuteResponse | null) => {
    setOpenTabs(tabs => tabs.map(t => t.id === activeTabId ? { ...t, response: resp } : t));
  };

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeEnvId, setActiveEnvId] = useState<number | undefined>();

  const [showEnvModal, setShowEnvModal] = useState(false);
  const [editingEnv, setEditingEnv] = useState<Environment | null>(null);
  const [envContextMenu, setEnvContextMenu] = useState<{ x: number; y: number; env: Environment } | null>(null);
  const [showFolderModal, setShowFolderModal] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState<{type: 'request' | 'folder', id: number, name: string} | null>(null);
  const [newEnvName, setNewEnvName] = useState('');
  const [newEnvBaseUrl, setNewEnvBaseUrl] = useState('');
  const [newEnvVars, setNewEnvVars] = useState<{ key: string; value: string }[]>([{ key: '', value: '' }]);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderParentId, setNewFolderParentId] = useState<number | undefined>();
  const [renameValue, setRenameValue] = useState('');
  const [requestTab, setRequestTab] = useState<'params' | 'body' | 'headers'>('params');
  const [responseTab, setResponseTab] = useState<'body' | 'headers'>('body');
  const [bodyViewMode, setBodyViewMode] = useState<'pretty' | 'raw' | 'preview'>('pretty');
  const [confirmModal, setConfirmModal] = useState<{message: string, onConfirm: () => void} | null>(null);
  const [activeHistoryId, setActiveHistoryId] = useState<number | null>(null);
  const [tabContextMenu, setTabContextMenu] = useState<{x: number, y: number, tabId: string} | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [showSavePanel, setShowSavePanel] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [showMethodDropdown, setShowMethodDropdown] = useState(false);
  const [showThemeDropdown, setShowThemeDropdown] = useState(false);
  const [responsePanelHeight, setResponsePanelHeight] = useState(300);
  const isResizingResponse = useRef(false);
  const responseContainerRef = useRef<HTMLDivElement>(null);
  const [showTabOverflow, setShowTabOverflow] = useState(false);
  const tabsContainerRef = useRef<HTMLDivElement>(null);
  const [overflowTabs, setOverflowTabs] = useState<string[]>([]);
  const isResizing = useRef(false);

  useEffect(() => {
    loadData();
    const handleClick = () => { setContextMenu(null); setTabContextMenu(null); setShowTabOverflow(false); setEnvContextMenu(null); };
    const handleContextMenuDismiss = () => { setTabContextMenu(null); setEnvContextMenu(null); };
    const handleKeyDown = (e: KeyboardEvent) => { if (e.key === 'Escape') { setContextMenu(null); setTabContextMenu(null); setShowTabOverflow(false); setEnvContextMenu(null); } };
    document.addEventListener('click', handleClick);
    document.addEventListener('contextmenu', handleContextMenuDismiss);
    document.addEventListener('keydown', handleKeyDown);

    const handleMouseMove = (e: MouseEvent) => {
      if (isResizing.current) {
        e.preventDefault();
        const newWidth = e.clientX - 48;
        setSidebarWidth(Math.max(180, Math.min(500, newWidth)));
      }
      if (isResizingResponse.current && responseContainerRef.current) {
        e.preventDefault();
        const containerRect = responseContainerRef.current.getBoundingClientRect();
        const newHeight = containerRect.bottom - e.clientY;
        setResponsePanelHeight(Math.max(100, Math.min(containerRect.height - 100, newHeight)));
      }
    };
    const handleMouseUp = () => {
      if (isResizing.current) {
        isResizing.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.body.classList.remove('resizing');
      }
      if (isResizingResponse.current) {
        isResizingResponse.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.body.classList.remove('resizing');
      }
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('click', handleClick);
      document.removeEventListener('contextmenu', handleContextMenuDismiss);
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const container = tabsContainerRef.current;
    if (!container) return;
    const checkOverflow = () => {
      const children = container.querySelectorAll<HTMLElement>('.editor-tab');
      const containerRight = container.getBoundingClientRect().right - 70;
      const hidden: string[] = [];
      children.forEach(child => {
        const tabId = child.getAttribute('data-tab-id');
        if (tabId && child.getBoundingClientRect().right > containerRight) {
          hidden.push(tabId);
        }
      });
      setOverflowTabs(hidden);
    };
    checkOverflow();
    const observer = new ResizeObserver(checkOverflow);
    observer.observe(container);
    return () => observer.disconnect();
  }, [openTabs, activeTabId]);

  const loadData = async () => {
    try {
      const [envs, hist, tree, standalone] = await Promise.all([
        api.environments.list(),
        api.history.list(),
        api.folders.tree(),
        api.folders.standaloneRequests(),
      ]);
      setEnvironments(envs);
      setHistory(hist);
      setFolders(tree);
      setStandaloneRequests(standalone);
      const active = envs.find(e => e.is_active);
      if (active) setActiveEnvId(active.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载数据失败');
    }
  };

  const toggleFolder = (id: number) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(id)) newExpanded.delete(id);
    else newExpanded.add(id);
    setExpandedFolders(newExpanded);
  };

  const handleContextMenu = (e: React.MouseEvent, type: ContextMenu['type'], targetId?: number, parentFolderId?: number) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, type, targetId, parentFolderId });
  };

  // Unified drag handlers
  const handleDragStart = (e: React.DragEvent, data: DragData) => {
    setDragData(data);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', JSON.stringify(data));
  };

  const handleDragOver = (e: React.DragEvent, itemId: number, itemType: DragItemType) => {
    e.preventDefault();
    if (!dragData) return;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const position = calcGapPosition(e.clientY, rect);
    setDropTarget({ type: 'gap', position, refId: itemId, refType: itemType });
  };

  const handleFolderDragOver = (e: React.DragEvent, folderId: number) => {
    e.preventDefault();
    if (!dragData) return;
    setDropTarget({ type: 'folder', targetFolderId: folderId });
  };

  // Helper: find all sibling requests of a given request
  const getSiblingRequests = (refId: number): Request[] => {
    // Check standalone requests
    if (standaloneRequests.some(r => r.id === refId)) {
      return standaloneRequests;
    }
    // Search recursively through folders
    const searchFolders = (flds: Folder[]): Request[] | null => {
      for (const folder of flds) {
        if (folder.requests.some(r => r.id === refId)) {
          return folder.requests;
        }
        const found = searchFolders(folder.children);
        if (found) return found;
      }
      return null;
    };
    return searchFolders(folders) || [];
  };

  // Helper: find all sibling folders of a given folder
  const getSiblingFolders = (refId: number): Folder[] => {
    // Check root-level folders
    if (folders.some(f => f.id === refId)) {
      return folders;
    }
    const searchFolders = (flds: Folder[]): Folder[] | null => {
      for (const folder of flds) {
        if (folder.children.some(f => f.id === refId)) {
          return folder.children;
        }
        const found = searchFolders(folder.children);
        if (found) return found;
      }
      return null;
    };
    return searchFolders(folders) || [];
  };

  const handleGapDrop = async (drag: DragData, target: DropTarget) => {
    if (drag.type === 'request' && target.refType === 'request') {
      const siblings = getSiblingRequests(target.refId!);
      const newOrder = reorderList(siblings, drag.id, target.refId!, target.position!);
      await api.requests.reorder(newOrder.map(r => r.id));
    } else if (drag.type === 'folder' && target.refType === 'folder') {
      const siblings = getSiblingFolders(target.refId!);
      const newOrder = reorderList(siblings, drag.id, target.refId!, target.position!);
      await api.folders.reorder(newOrder.map(f => f.id));
    }
  };

  const handleFolderDrop = async (drag: DragData, target: DropTarget) => {
    if (drag.type === 'request') {
      await api.requests.update(drag.id, { folder_id: target.targetFolderId });
    } else if (drag.type === 'folder') {
      await api.folders.update(drag.id, { parent_folder_id: target.targetFolderId });
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    if (!dragData || !dropTarget) return;
    try {
      if (dropTarget.type === 'gap') {
        await handleGapDrop(dragData, dropTarget);
      } else if (dropTarget.type === 'folder') {
        await handleFolderDrop(dragData, dropTarget);
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    } finally {
      setDragData(null);
      setDropTarget(null);
    }
  };

  const handleDragEnd = () => {
    setDragData(null);
    setDropTarget(null);
  };

  const renderGapIndicator = (position: 'before' | 'after', itemId: number) => {
    const isActive = dropTarget?.type === 'gap'
      && dropTarget.refId === itemId
      && dropTarget.position === position;
    if (!isActive) return null;
    return <div className="gap-indicator" />;
  };

  const executeRequest = async () => {
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const headers = Object.fromEntries(currentRequest.headers.filter(h => h.key && h.enabled).map(h => [h.key, h.value]));
      const queryParams = Object.fromEntries(currentRequest.queryParams.filter(p => p.key && p.enabled).map(p => [p.key, p.value]));
      const result = await api.execute.adhoc({
        name: currentRequest.name,
        method: currentRequest.method,
        url: currentRequest.url,
        headers,
        query_params: queryParams,
        body: currentRequest.body || undefined,
        body_type: currentRequest.body ? 'json' : undefined,
      }, activeEnvId);
      setResponse(result);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败');
    } finally {
      setLoading(false);
    }
  };

  const saveRequest = async (nameOverride?: string) => {
    try {
      const name = nameOverride || currentRequest.name;
      const headers = Object.fromEntries(currentRequest.headers.filter(h => h.key && h.enabled).map(h => [h.key, h.value]));
      const queryParams = Object.fromEntries(currentRequest.queryParams.filter(p => p.key && p.enabled).map(p => [p.key, p.value]));
      if (currentRequest.id) {
        await api.requests.update(currentRequest.id, {
          name, method: currentRequest.method, url: currentRequest.url,
          headers, query_params: queryParams, body: currentRequest.body || undefined,
          folder_id: currentRequest.folder_id,
        });
      } else {
        const created = await api.requests.create({
          name, method: currentRequest.method, url: currentRequest.url,
          headers, query_params: queryParams, body: currentRequest.body || undefined,
          folder_id: currentRequest.folder_id,
        });
        setCurrentRequest({ ...currentRequest, id: created.id, name });
      }
      if (nameOverride) {
        setOpenTabs(tabs => tabs.map(t => t.id === activeTabId ? { ...t, name, dirty: false } : t));
      } else {
        setOpenTabs(tabs => tabs.map(t => t.id === activeTabId ? { ...t, dirty: false } : t));
      }
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败');
    }
  };

  const handleSaveClick = () => {
    setSaveName(currentRequest.name || '');
    setShowSavePanel(true);
  };

  const handleSaveConfirm = async () => {
    if (!saveName.trim()) return;
    await saveRequest(saveName.trim());
    setShowSavePanel(false);
    setSaveName('');
  };

  const loadRequest = (req: Request) => {
    const existing = openTabs.find(t => t.requestId === req.id);
    if (existing) { setActiveTabId(existing.id); return; }
    const newId = makeTabId();
    const newTab: RequestTab = {
      id: newId, requestId: req.id, name: req.name, method: req.method as HttpMethod, url: req.url,
      headers: Object.entries(req.headers || {}).map(([key, value]) => ({ key, value, description: '', enabled: true })).concat([emptyParam()]),
      queryParams: Object.entries(req.query_params || {}).map(([key, value]) => ({ key, value, description: '', enabled: true })).concat([emptyParam()]),
      body: req.body || '', folder_id: req.folder_id || undefined, response: null, dirty: false,
    };
    setOpenTabs(tabs => [...tabs, newTab]);
    setActiveTabId(newId);
  };

  const newRequest = (folderId?: number) => {
    const newId = makeTabId();
    const newTab: RequestTab = {
      id: newId, name: '新建请求', method: 'GET', url: '',
      headers: [emptyParam()], queryParams: [emptyParam()],
      body: '', folder_id: folderId, response: null, dirty: true,
    };
    setOpenTabs(tabs => [...tabs, newTab]);
    setActiveTabId(newId);
  };

  const closeTab = (tabId: string) => {
    setOpenTabs(tabs => {
      const remaining = tabs.filter(t => t.id !== tabId);
      if (activeTabId === tabId) {
        if (remaining.length > 0) {
          const idx = tabs.findIndex(t => t.id === tabId);
          const newActive = remaining[Math.min(idx, remaining.length - 1)];
          setActiveTabId(newActive.id);
        } else { setActiveTabId(''); }
      }
      return remaining;
    });
  };

  const closeOtherTabs = (tabId: string) => {
    setOpenTabs(tabs => {
      const keep = tabs.filter(t => t.id === tabId);
      if (keep.length === 0) return tabs;
      setActiveTabId(tabId);
      return keep;
    });
  };

  const closeAllTabs = () => { setOpenTabs([]); setActiveTabId(''); };

  const deleteRequest = async (id: number) => {
    setConfirmModal({
      message: '确定删除此请求？',
      onConfirm: async () => {
        await api.requests.delete(id);
        loadData();
        const tab = openTabs.find(t => t.requestId === id);
        if (tab) closeTab(tab.id);
        setConfirmModal(null);
      }
    });
  };

  const duplicateRequest = async (req: Request) => {
    await api.requests.create({
      name: `${req.name} (副本)`, method: req.method as HttpMethod, url: req.url,
      headers: req.headers, query_params: req.query_params,
      body: req.body || undefined, folder_id: req.folder_id || undefined,
    });
    loadData();
  };

  const renameItem = async () => {
    if (!showRenameModal || !renameValue.trim()) return;
    if (showRenameModal.type === 'folder') {
      await api.folders.update(showRenameModal.id, { name: renameValue });
    } else {
      await api.requests.update(showRenameModal.id, { name: renameValue });
    }
    setShowRenameModal(null);
    setRenameValue('');
    loadData();
  };

  const loadFromHistory = (h: History) => {
    const newId = makeTabId();
    const newTab: RequestTab = {
      id: newId, name: `历史记录 - ${h.method}`, method: h.method as HttpMethod, url: h.url,
      headers: Object.entries(h.request_headers || {}).map(([key, value]) => ({ key, value, description: '', enabled: true })).concat([emptyParam()]),
      queryParams: [emptyParam()], body: h.request_body || '',
      response: {
        status_code: h.status_code, status_text: h.status_text, headers: h.response_headers,
        body: h.response_body, body_json: tryParseJson(h.response_body),
        response_time_ms: h.response_time_ms, response_size: h.response_size, warnings: [],
      }, dirty: true,
    };
    setOpenTabs(tabs => [...tabs, newTab]);
    setActiveTabId(newId);
  };

  const tryParseJson = (str: string | null): unknown => {
    if (!str) return null;
    try { return JSON.parse(str); } catch { return null; }
  };

  const formatTimeAgo = (dateStr: string): string => {
    const diffMs = new Date().getTime() - new Date(dateStr).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return `${mins}分钟前`;
    const hours = Math.floor(diffMs / 3600000);
    if (hours < 24) return `${hours}小时前`;
    return `${Math.floor(diffMs / 86400000)}天前`;
  };

  const createEnvironment = async () => {
    if (!newEnvName.trim()) return;
    await api.environments.create({ name: newEnvName, base_url: newEnvBaseUrl, variables: newEnvVars.filter(v => v.key.trim()) });
    setShowEnvModal(false);
    setNewEnvName('');
    setNewEnvBaseUrl('');
    setNewEnvVars([{ key: '', value: '' }]);
    loadData();
  };

  const openEditEnv = (env: Environment) => {
    setEditingEnv(env);
    setNewEnvName(env.name);
    setNewEnvBaseUrl(env.base_url || '');
    setNewEnvVars(env.variables.length > 0
      ? env.variables.map(v => ({ key: v.key, value: v.value })).concat([{ key: '', value: '' }])
      : [{ key: '', value: '' }]);
  };

  const saveEditEnv = async () => {
    if (!editingEnv || !newEnvName.trim()) return;
    await api.environments.update(editingEnv.id, { name: newEnvName, base_url: newEnvBaseUrl });
    for (const v of editingEnv.variables) { await api.environments.deleteVariable(v.id); }
    for (const v of newEnvVars.filter(v => v.key.trim())) { await api.environments.addVariable(editingEnv.id, v); }
    setEditingEnv(null);
    setNewEnvName('');
    setNewEnvBaseUrl('');
    setNewEnvVars([{ key: '', value: '' }]);
    loadData();
  };

  const deleteEnvironment = async (id: number) => {
    setConfirmModal({
      message: '确定删除此环境？',
      onConfirm: async () => {
        await api.environments.delete(id);
        if (activeEnvId === id) setActiveEnvId(undefined);
        loadData();
        setConfirmModal(null);
      }
    });
  };

  const activateEnvironment = async (id: number) => {
    await api.environments.activate(id);
    setActiveEnvId(id);
    loadData();
  };

  const createFolder = async () => {
    if (!newFolderName.trim()) return;
    await api.folders.create({ name: newFolderName, parent_folder_id: newFolderParentId });
    setShowFolderModal(false);
    setNewFolderName('');
    setNewFolderParentId(undefined);
    if (newFolderParentId) setExpandedFolders(prev => new Set([...prev, newFolderParentId]));
    loadData();
  };

  const deleteFolder = async (id: number) => {
    setConfirmModal({
      message: '确定删除此文件夹及其所有内容？',
      onConfirm: async () => {
        await api.folders.delete(id);
        loadData();
        setConfirmModal(null);
      }
    });
  };

  const renderFolderTree = (folder: Folder, depth: number) => {
    const isExpanded = expandedFolders.has(folder.id);
    const isFolderDropTarget = dropTarget?.type === 'folder' && dropTarget.targetFolderId === folder.id;
    return (
      <div key={folder.id}>
        {renderGapIndicator('before', folder.id)}
        <div
          className={`tree-item folder-item ${isFolderDropTarget ? 'drag-over-folder' : ''} ${dragData?.id === folder.id && dragData?.type === 'folder' ? 'dragging' : ''}`}
          style={{ paddingLeft: `${12 + depth * 16}px` }}
          onClick={() => toggleFolder(folder.id)}
          onContextMenu={(e) => handleContextMenu(e, 'folder', folder.id)}
          draggable
          onDragStart={(e) => handleDragStart(e, { type: 'folder', id: folder.id })}
          onDragOver={(e) => {
            const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
            const relativeY = e.clientY - rect.top;
            const threshold = rect.height * 0.25;
            if (relativeY < threshold || relativeY > rect.height - threshold) {
              handleDragOver(e, folder.id, 'folder');
            } else {
              handleFolderDragOver(e, folder.id);
            }
          }}
          onDrop={handleDrop}
          onDragEnd={handleDragEnd}
        >
          <span className="drag-handle">⋮⋮</span>
          <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▶</span>
          <span className="folder-icon">{Icons.folder()}</span>
          <span className="item-name">{folder.name}</span>
          <span className="item-count">{folder.children.length + folder.requests.length}</span>
        </div>
        {renderGapIndicator('after', folder.id)}
        {isExpanded && (
          <div className="tree-children">
            {folder.children.map(child => renderFolderTree(child, depth + 1))}
            {folder.requests.map(req => renderRequestItem(req, depth + 1))}
            {folder.children.length === 0 && folder.requests.length === 0 && (
              <div className="empty-hint" style={{ paddingLeft: `${12 + (depth + 1) * 16}px` }}>空文件夹</div>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderRequestItem = (req: Request, indent: number = 0) => (
    <div key={req.id}>
      {renderGapIndicator('before', req.id)}
      <div
        className={`tree-item request-item ${currentRequest.id === req.id ? 'active' : ''} ${dragData?.id === req.id && dragData?.type === 'request' ? 'dragging' : ''}`}
        style={{ paddingLeft: `${12 + indent * 16}px` }}
        onClick={() => loadRequest(req)}
        onContextMenu={(e) => handleContextMenu(e, 'request', req.id)}
        draggable
        onDragStart={(e) => handleDragStart(e, { type: 'request', id: req.id, folderId: req.folder_id })}
        onDragOver={(e) => handleDragOver(e, req.id, 'request')}
        onDrop={handleDrop}
        onDragEnd={handleDragEnd}
      >
        <span className="drag-handle">⋮⋮</span>
        <span className="method-text" style={{ color: METHOD_COLORS[req.method as HttpMethod] }}>{req.method}</span>
        <span className="item-name">{req.name}</span>
      </div>
      {renderGapIndicator('after', req.id)}
    </div>
  );

  const renderContextMenu = () => {
    if (!contextMenu) return null;
    return (
      <div className="context-menu" style={{ left: contextMenu.x, top: contextMenu.y }} onClick={e => e.stopPropagation()}>
        {contextMenu.type === 'background' && (
          <>
            <div className="menu-item" onClick={() => { newRequest(); setContextMenu(null); }}><span className="menu-icon">{Icons.plus()}</span> 新建请求</div>
            <div className="menu-item" onClick={() => { setShowFolderModal(true); setNewFolderParentId(undefined); setContextMenu(null); }}><span className="menu-icon">{Icons.folder()}</span> 新建文件夹</div>
          </>
        )}
        {contextMenu.type === 'request' && contextMenu.targetId && (
          <>
            <div className="menu-item" onClick={() => {
              const allReqs = [...standaloneRequests];
              const findReq = (flds: Folder[]): Request | undefined => {
                for (const f of flds) {
                  const r = f.requests.find(r => r.id === contextMenu.targetId);
                  if (r) return r;
                  const found = findReq(f.children);
                  if (found) return found;
                }
                return undefined;
              };
              const req = allReqs.find(r => r.id === contextMenu.targetId) || findReq(folders);
              if (req) duplicateRequest(req);
              setContextMenu(null);
            }}><span className="menu-icon">{Icons.copy()}</span> 复制</div>
            <div className="menu-item" onClick={() => {
              const allReqs = [...standaloneRequests];
              const findReq = (flds: Folder[]): Request | undefined => {
                for (const f of flds) {
                  const r = f.requests.find(r => r.id === contextMenu.targetId);
                  if (r) return r;
                  const found = findReq(f.children);
                  if (found) return found;
                }
                return undefined;
              };
              const req = allReqs.find(r => r.id === contextMenu.targetId) || findReq(folders);
              if (req) { setShowRenameModal({ type: 'request', id: req.id, name: req.name }); setRenameValue(req.name); }
              setContextMenu(null);
            }}><span className="menu-icon">{Icons.edit()}</span> 重命名</div>
            <div className="menu-item danger" onClick={() => { deleteRequest(contextMenu.targetId!); setContextMenu(null); }}><span className="menu-icon">{Icons.trash()}</span> 删除</div>
          </>
        )}
        {contextMenu.type === 'folder' && contextMenu.targetId && (
          <>
            <div className="menu-item" onClick={() => { setShowFolderModal(true); setNewFolderParentId(contextMenu.targetId); setContextMenu(null); }}><span className="menu-icon">{Icons.folder()}</span> 新建子文件夹</div>
            <div className="menu-item" onClick={() => {
              const findFolder = (flds: Folder[]): Folder | undefined => {
                for (const f of flds) {
                  if (f.id === contextMenu.targetId) return f;
                  const found = findFolder(f.children);
                  if (found) return found;
                }
                return undefined;
              };
              const folder = findFolder(folders);
              if (folder) { setShowRenameModal({ type: 'folder', id: folder.id, name: folder.name }); setRenameValue(folder.name); }
              setContextMenu(null);
            }}><span className="menu-icon">{Icons.edit()}</span> 重命名</div>
            <div className="menu-item danger" onClick={() => { deleteFolder(contextMenu.targetId!); setContextMenu(null); }}><span className="menu-icon">{Icons.trash()}</span> 删除</div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="app" onContextMenu={e => e.preventDefault()}>
      <header className="header">
        <h1 className="brand"><span className="brand-api">API</span><span className="brand-ok">OK</span></h1>
        <div className="header-right">
          <div className="theme-picker" tabIndex={0} onBlur={() => setTimeout(() => setShowThemeDropdown(false), 150)}>
            <div className="theme-picker-trigger" onClick={() => setShowThemeDropdown(!showThemeDropdown)}>
              <span className="theme-picker-dot" style={{ background: THEMES.find(t => t.id === theme)?.color }} />
              <span className="theme-picker-arrow">▾</span>
            </div>
            {showThemeDropdown && (
              <div className="theme-picker-menu">
                {THEMES.map(t => (
                  <div key={t.id} className={`theme-picker-item ${theme === t.id ? 'active' : ''}`} onClick={() => { setTheme(t.id); setShowThemeDropdown(false); }}>
                    <span className="theme-picker-dot" style={{ background: t.color }} />
                    <span>{t.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <select value={activeEnvId || ''} onChange={e => {
            const id = e.target.value ? Number(e.target.value) : undefined;
            setActiveEnvId(id);
            if (id) activateEnvironment(id);
          }} className="env-select">
            <option value="">无环境</option>
            {environments.map(env => <option key={env.id} value={env.id}>{env.name} ({env.variables.length} 个变量)</option>)}
          </select>
        </div>
      </header>

      <div className="main">
        <nav className="activity-bar">
          <button className={activeTab === 'requests' ? 'active' : ''} onClick={() => setActiveTab('requests')} title="接口管理">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          </button>
          <button className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')} title="请求历史">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </button>
          <button className={activeTab === 'environments' ? 'active' : ''} onClick={() => setActiveTab('environments')} title="环境管理">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          </button>
        </nav>
        <aside className="sidebar" style={{ width: sidebarWidth }}>

          {activeTab === 'requests' && (
            <div className="list" onContextMenu={(e) => handleContextMenu(e, 'background')}>
              <div className="tree-view" onDragOver={(e) => e.preventDefault()} onDrop={handleDrop}>
                {folders.map(folder => renderFolderTree(folder, 0))}
                {standaloneRequests.map(req => renderRequestItem(req, 0))}
                {folders.length === 0 && standaloneRequests.length === 0 && (
                  <div className="empty">右键创建</div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'history' && (
            <div className="list">
              {history.length > 0 && <button className="clear-btn" onClick={() => { setConfirmModal({ message: '确定清空全部？', onConfirm: async () => { await api.history.clear(); loadData(); setConfirmModal(null); } }); }}>{Icons.trash(12)} 清空全部</button>}
              {history.map(h => (
                <div key={h.id} className={`list-item history-item ${activeHistoryId === h.id ? 'active' : ''}`} onClick={() => { loadFromHistory(h); setActiveHistoryId(h.id); }}>
                  <span className="method-text" style={{ color: METHOD_COLORS[h.method as HttpMethod] || '#666' }}>{h.method}</span>
                  <span className="status-badge" style={{ color: h.status_code < 400 ? '#49cc90' : '#f93e3e' }}>{h.status_code}</span>
                  <span className="url" title={h.url}>{h.url.length > 20 ? h.url.slice(0, 20) + '...' : h.url}</span>
                  <span className="time-ago">{formatTimeAgo(h.executed_at)}</span>
                  <button className="delete-btn" onClick={e => { e.stopPropagation(); api.history.delete(h.id).then(loadData); }}>×</button>
                </div>
              ))}
              {history.length === 0 && <div className="empty">暂无历史记录</div>}
            </div>
          )}

          {activeTab === 'environments' && (
            <div className="list">
              <button className="new-btn" onClick={() => setShowEnvModal(true)}>+ 新建环境</button>
              {environments.map(env => (
                <div key={env.id} className={`tree-item env-item ${env.is_active ? 'active-env-item' : ''}`} onClick={() => openEditEnv(env)} onContextMenu={e => { e.preventDefault(); e.stopPropagation(); setEnvContextMenu({ x: e.clientX, y: e.clientY, env }); }}>
                  <span className="env-active-dot" style={{ opacity: env.is_active ? 1 : 0 }} />
                  <span className="item-name">{env.name}</span>
                  {env.base_url && <span className="env-base-url-hint">{env.base_url.replace(/^https?:\/\//, '').slice(0, 20)}</span>}
                  <span className="item-count">{env.variables.length}</span>
                </div>
              ))}
              {environments.length === 0 && <div className="empty">暂无环境</div>}
            </div>
          )}
        </aside>
        <div className="sidebar-resize" onMouseDown={(e) => { e.preventDefault(); isResizing.current = true; document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none'; document.body.classList.add('resizing'); }} />

        <main className="content">
          <div className="editor-tabs" ref={tabsContainerRef}>
            {openTabs.map(tab => (
              <div key={tab.id} data-tab-id={tab.id} className={`editor-tab ${tab.id === activeTabId ? 'active' : ''}`} onClick={() => setActiveTabId(tab.id)} onContextMenu={e => { e.preventDefault(); e.stopPropagation(); setTabContextMenu({ x: e.clientX, y: e.clientY, tabId: tab.id }); }}>
                <span className="editor-tab-method" style={{ color: METHOD_COLORS[tab.method] }}>{tab.method}</span>
                <span className="editor-tab-name">{tab.name}</span>
                {tab.dirty && <span className="editor-tab-dirty" />}
                <button className="editor-tab-close" onClick={e => { e.stopPropagation(); closeTab(tab.id); }}>×</button>
              </div>
            ))}
            <div className="editor-tabs-actions">
              <button className="editor-tab-add" onClick={() => newRequest()}>+</button>
              {overflowTabs.length > 0 && (
                <div className="tab-overflow-wrapper">
                  <button className="tab-overflow-btn" onClick={() => setShowTabOverflow(!showTabOverflow)} title={`还有 ${overflowTabs.length} 个标签`}>
                    ··· <span className="tab-overflow-count">{overflowTabs.length}</span>
                  </button>
                  {showTabOverflow && (
                    <div className="tab-overflow-menu">
                      {openTabs.filter(t => overflowTabs.includes(t.id)).map(tab => (
                        <div key={tab.id} className={`tab-overflow-item ${tab.id === activeTabId ? 'active' : ''}`} onClick={() => { setActiveTabId(tab.id); setShowTabOverflow(false); }}>
                          <span className="tab-overflow-method" style={{ color: METHOD_COLORS[tab.method] }}>{tab.method}</span>
                          <span className="tab-overflow-name">{tab.name}</span>
                          <button className="tab-overflow-close" onClick={e => { e.stopPropagation(); closeTab(tab.id); }}>×</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          {openTabs.length === 0 && (
            <div className="empty-content">
              <p>点击左侧请求或点击 + 新建请求</p>
            </div>
          )}

          {currentTab && (
          <>
          <div className="split-container" ref={responseContainerRef}>
            <div className="request-builder" style={response ? { flex: 'none', height: `calc(100% - ${responsePanelHeight}px - 6px)` } : undefined}>
            <div className="url-bar">
              <div className="method-dropdown" tabIndex={0} onBlur={() => setTimeout(() => setShowMethodDropdown(false), 150)}>
                <div className="method-dropdown-trigger" style={{ color: METHOD_COLORS[currentRequest.method] }} onClick={() => setShowMethodDropdown(!showMethodDropdown)}>
                  <span>{currentRequest.method}</span>
                  <span className="method-dropdown-arrow">▾</span>
                </div>
                {showMethodDropdown && (
                  <div className="method-dropdown-menu">
                    {HTTP_METHODS.map(m => (
                      <div key={m} className={`method-dropdown-item ${currentRequest.method === m ? 'active' : ''}`} style={{ color: METHOD_COLORS[m] }} onClick={() => { setCurrentRequest({ ...currentRequest, method: m }); setShowMethodDropdown(false); }}>
                        {m}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <input type="text" value={currentRequest.url} onChange={e => setCurrentRequest({ ...currentRequest, url: e.target.value })} placeholder="输入 URL（支持 {{变量}} 语法）" className="url-input" />
              <button onClick={executeRequest} disabled={loading || !currentRequest.url} className="send-btn">{loading ? '发送中...' : '发送'}</button>
              <button onClick={handleSaveClick} className="save-btn">保存</button>
            </div>

            <div className="params-section">
              <div className="params-tabs">
                <button className={requestTab === 'params' ? 'active' : ''} onClick={() => setRequestTab('params')}>查询参数</button>
                <button className={requestTab === 'body' ? 'active' : ''} onClick={() => setRequestTab('body')}>请求体</button>
                <button className={requestTab === 'headers' ? 'active' : ''} onClick={() => setRequestTab('headers')}>请求头</button>
              </div>
              <div className="params-content">
                {requestTab === 'params' && (
                  <table className="param-table">
                    <thead><tr><th className="param-th-check"></th><th>Key</th><th>Value</th><th>Description</th><th className="param-th-action"></th></tr></thead>
                    <tbody>
                      {currentRequest.queryParams.map((p, i) => (
                        <tr key={i} className={!p.enabled ? 'param-disabled' : ''}>
                          <td className="param-td-check"><input type="checkbox" checked={p.enabled} onChange={e => { const queryParams = [...currentRequest.queryParams]; queryParams[i] = { ...queryParams[i], enabled: e.target.checked }; setCurrentRequest({ ...currentRequest, queryParams }); }} /></td>
                          <td><input placeholder="Key" value={p.key} onChange={e => { const queryParams = [...currentRequest.queryParams]; queryParams[i] = { ...queryParams[i], key: e.target.value }; if (i === queryParams.length - 1 && e.target.value) queryParams.push(emptyParam()); setCurrentRequest({ ...currentRequest, queryParams }); }} /></td>
                          <td><input placeholder="Value" value={p.value} onChange={e => { const queryParams = [...currentRequest.queryParams]; queryParams[i] = { ...queryParams[i], value: e.target.value }; setCurrentRequest({ ...currentRequest, queryParams }); }} /></td>
                          <td><input placeholder="Description" value={p.description} onChange={e => { const queryParams = [...currentRequest.queryParams]; queryParams[i] = { ...queryParams[i], description: e.target.value }; setCurrentRequest({ ...currentRequest, queryParams }); }} /></td>
                          <td className="param-td-action">{p.key && <button className="remove-param" onClick={() => { const queryParams = currentRequest.queryParams.filter((_, idx) => idx !== i); if (!queryParams.length || queryParams[queryParams.length - 1].key) queryParams.push(emptyParam()); setCurrentRequest({ ...currentRequest, queryParams }); }}>×</button>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {requestTab === 'body' && (
                  <textarea value={currentRequest.body} onChange={e => setCurrentRequest({ ...currentRequest, body: e.target.value })} placeholder='{"key": "value"}' rows={10} />
                )}
                {requestTab === 'headers' && (
                  <table className="param-table">
                    <thead><tr><th className="param-th-check"></th><th>Key</th><th>Value</th><th>Description</th><th className="param-th-action"></th></tr></thead>
                    <tbody>
                      {currentRequest.headers.map((h, i) => (
                        <tr key={i} className={!h.enabled ? 'param-disabled' : ''}>
                          <td className="param-td-check"><input type="checkbox" checked={h.enabled} onChange={e => { const headers = [...currentRequest.headers]; headers[i] = { ...headers[i], enabled: e.target.checked }; setCurrentRequest({ ...currentRequest, headers }); }} /></td>
                          <td><input placeholder="Key" value={h.key} onChange={e => { const headers = [...currentRequest.headers]; headers[i] = { ...headers[i], key: e.target.value }; if (i === headers.length - 1 && e.target.value) headers.push(emptyParam()); setCurrentRequest({ ...currentRequest, headers }); }} /></td>
                          <td><input placeholder="Value" value={h.value} onChange={e => { const headers = [...currentRequest.headers]; headers[i] = { ...headers[i], value: e.target.value }; setCurrentRequest({ ...currentRequest, headers }); }} /></td>
                          <td><input placeholder="Description" value={h.description} onChange={e => { const headers = [...currentRequest.headers]; headers[i] = { ...headers[i], description: e.target.value }; setCurrentRequest({ ...currentRequest, headers }); }} /></td>
                          <td className="param-td-action">{h.key && <button className="remove-param" onClick={() => { const headers = currentRequest.headers.filter((_, idx) => idx !== i); if (!headers.length || headers[headers.length - 1].key) headers.push(emptyParam()); setCurrentRequest({ ...currentRequest, headers }); }}>×</button>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          {error && <div className="error">{error}</div>}

          {response && (
            <>
            <div className="response-resize-handle" onMouseDown={(e) => { e.preventDefault(); isResizingResponse.current = true; document.body.style.cursor = 'row-resize'; document.body.style.userSelect = 'none'; document.body.classList.add('resizing'); }} />
            <div className="response-panel" style={{ height: responsePanelHeight }}>
              <div className="response-status-bar">
                <span className="status-dot-inline" style={{ backgroundColor: response.status_code < 400 ? '#49cc90' : '#f93e3e' }} />
                <span className="status-code" style={{ color: response.status_code < 400 ? '#49cc90' : '#f93e3e' }}>{response.status_code} {response.status_text}</span>
                <span className="resp-meta">{response.response_time_ms}ms</span>
                <span className="resp-meta">{response.response_size}B</span>
              </div>
              {response.warnings.length > 0 && <div className="warnings">{response.warnings.map((w, i) => <div key={i}>{Icons.warning(12)} {w}</div>)}</div>}
              <div className="response-tabs">
                <button className={responseTab === 'body' ? 'active' : ''} onClick={() => setResponseTab('body')}>响应体</button>
                <button className={responseTab === 'headers' ? 'active' : ''} onClick={() => setResponseTab('headers')}>响应头</button>
              </div>
              <div className="response-content">
                {responseTab === 'body' && (() => {
                  const contentType = (response.headers?.['content-type'] || response.headers?.['Content-Type'] || '').toLowerCase();
                  const tag = contentType.includes('json') ? 'JSON'
                    : contentType.includes('html') ? 'HTML'
                    : contentType.includes('xml') ? 'XML'
                    : contentType.includes('javascript') ? 'JS'
                    : contentType.includes('css') ? 'CSS'
                    : contentType.includes('image') ? 'IMAGE'
                    : contentType.includes('video') ? 'VIDEO'
                    : contentType.includes('audio') ? 'AUDIO'
                    : contentType.includes('pdf') ? 'PDF'
                    : contentType.includes('text') ? 'TEXT'
                    : 'RAW';
                  const prettyText = response.body_json ? JSON.stringify(response.body_json, null, 2) : response.body || '(空)';
                  const rawText = response.body || '(空)';
                  const lang = tag === 'JSON' ? 'json' : tag === 'HTML' ? 'html' : tag === 'XML' ? 'xml' : tag === 'JS' ? 'javascript' : tag === 'CSS' ? 'css' : 'plaintext';
                  return (
                    <div className="code-block">
                      <div className="code-block-toolbar">
                        <span className="code-block-tag">{tag}</span>
                        <div className="body-view-modes">
                          <button className={bodyViewMode === 'pretty' ? 'active' : ''} onClick={() => setBodyViewMode('pretty')}>格式化</button>
                          <button className={bodyViewMode === 'raw' ? 'active' : ''} onClick={() => setBodyViewMode('raw')}>原始数据</button>
                          <button className={bodyViewMode === 'preview' ? 'active' : ''} onClick={() => setBodyViewMode('preview')}>预览</button>
                        </div>
                      </div>
                      {bodyViewMode === 'pretty' && (
                        <SyntaxHighlighter language={lang} style={githubGist} showLineNumbers wrapLongLines={false}
                          customStyle={{ margin: 0, padding: '14px 0', flex: 1, fontSize: '0.8rem', background: '#fff', overflow: 'auto' }}
                          lineNumberStyle={{ minWidth: '44px', paddingRight: '14px', color: '#b0b0b0', textAlign: 'right', userSelect: 'none' }}>
                          {prettyText}
                        </SyntaxHighlighter>
                      )}
                      {bodyViewMode === 'raw' && <pre className="raw-pre">{rawText}</pre>}
                      {bodyViewMode === 'preview' && (
                        <div className="preview-frame">
                          {(tag === 'HTML' || tag === 'XML') ? <iframe title="preview" srcDoc={rawText} sandbox="allow-same-origin" className="preview-iframe" />
                          : contentType.includes('image') ? <div className="preview-media"><img src={currentRequest.url} alt="response preview" className="preview-img" /></div>
                          : contentType.includes('video') ? <div className="preview-media"><video src={currentRequest.url} controls className="preview-video" /></div>
                          : contentType.includes('audio') ? <div className="preview-media"><audio src={currentRequest.url} controls /></div>
                          : contentType.includes('pdf') ? <iframe title="pdf preview" src={currentRequest.url} className="preview-iframe" />
                          : tag === 'JSON' ? <pre className="raw-pre">{prettyText}</pre>
                          : <pre className="raw-pre">{rawText}</pre>}
                        </div>
                      )}
                    </div>
                  );
                })()}
                {responseTab === 'headers' && (
                  <table className="headers-table">
                    <thead><tr><th>名称</th><th>值</th></tr></thead>
                    <tbody>{Object.entries(response.headers || {}).map(([key, value]) => <tr key={key}><td>{key}</td><td>{String(value)}</td></tr>)}</tbody>
                  </table>
                )}
              </div>
            </div>
            </>
          )}
          </div>
          </>
          )}
        </main>
      </div>

      {renderContextMenu()}

      {tabContextMenu && (
        <div className="context-menu" style={{ left: tabContextMenu.x, top: tabContextMenu.y }} onClick={e => e.stopPropagation()}>
          <div className="menu-item" onClick={() => { closeTab(tabContextMenu.tabId); setTabContextMenu(null); }}>关闭当前标签页</div>
          <div className="menu-item" onClick={() => { closeOtherTabs(tabContextMenu.tabId); setTabContextMenu(null); }}>关闭其他标签页</div>
          <div className="menu-item danger" onClick={() => { closeAllTabs(); setTabContextMenu(null); }}>关闭全部标签页</div>
        </div>
      )}

      {envContextMenu && (
        <div className="context-menu" style={{ left: envContextMenu.x, top: envContextMenu.y }} onClick={e => e.stopPropagation()}>
          {!envContextMenu.env.is_active && <div className="menu-item" onClick={() => { activateEnvironment(envContextMenu.env.id); setEnvContextMenu(null); }}><span className="menu-icon">{Icons.plus()}</span> 激活</div>}
          {envContextMenu.env.is_active && <div className="menu-item" onClick={async () => { await api.environments.deactivate(envContextMenu.env.id); setActiveEnvId(undefined); loadData(); setEnvContextMenu(null); }}><span className="menu-icon">{Icons.plus()}</span> 取消激活</div>}
          <div className="menu-item" onClick={() => { openEditEnv(envContextMenu.env); setEnvContextMenu(null); }}><span className="menu-icon">{Icons.edit()}</span> 编辑</div>
          <div className="menu-item danger" onClick={() => { deleteEnvironment(envContextMenu.env.id); setEnvContextMenu(null); }}><span className="menu-icon">{Icons.trash()}</span> 删除</div>
        </div>
      )}

      {showEnvModal && (
        <div className="modal-overlay" onClick={() => setShowEnvModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>创建环境</h2>
            <input type="text" placeholder="环境名称" value={newEnvName} onChange={e => setNewEnvName(e.target.value)} className="modal-input" />
            <input type="text" placeholder="Base URL（如 https://api.example.com）" value={newEnvBaseUrl} onChange={e => setNewEnvBaseUrl(e.target.value)} className="modal-input" style={{ marginTop: 8 }} />
            <h3>变量</h3>
            {newEnvVars.map((v, i) => (
              <div key={i} className="param-row">
                <input placeholder="键" value={v.key} onChange={e => { const vars = [...newEnvVars]; vars[i].key = e.target.value; if (i === vars.length - 1 && e.target.value) vars.push({ key: '', value: '' }); setNewEnvVars(vars); }} />
                <input placeholder="值" value={v.value} onChange={e => { const vars = [...newEnvVars]; vars[i].value = e.target.value; setNewEnvVars(vars); }} />
              </div>
            ))}
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowEnvModal(false)}>取消</button>
              <button className="create-btn" onClick={createEnvironment}>创建</button>
            </div>
          </div>
        </div>
      )}

      {editingEnv && (
        <div className="modal-overlay" onClick={() => { setEditingEnv(null); setNewEnvName(''); setNewEnvBaseUrl(''); setNewEnvVars([{ key: '', value: '' }]); }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>编辑环境</h2>
            <input type="text" placeholder="环境名称" value={newEnvName} onChange={e => setNewEnvName(e.target.value)} className="modal-input" autoFocus />
            <input type="text" placeholder="Base URL（如 https://api.example.com）" value={newEnvBaseUrl} onChange={e => setNewEnvBaseUrl(e.target.value)} className="modal-input" style={{ marginTop: 8 }} />
            <h3>变量</h3>
            {newEnvVars.map((v, i) => (
              <div key={i} className="param-row">
                <input placeholder="键" value={v.key} onChange={e => { const vars = [...newEnvVars]; vars[i].key = e.target.value; if (i === vars.length - 1 && e.target.value) vars.push({ key: '', value: '' }); setNewEnvVars(vars); }} />
                <input placeholder="值" value={v.value} onChange={e => { const vars = [...newEnvVars]; vars[i].value = e.target.value; setNewEnvVars(vars); }} />
              </div>
            ))}
            <div className="modal-actions">
              <div style={{ display: 'flex', gap: 8 }}>
                {!editingEnv.is_active && <button className="activate-btn" onClick={async () => { await activateEnvironment(editingEnv.id); setEditingEnv({ ...editingEnv, is_active: true }); }}>激活</button>}
                <button className="delete-btn-modal" onClick={() => { deleteEnvironment(editingEnv.id); setEditingEnv(null); }}>删除</button>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="cancel-btn" onClick={() => { setEditingEnv(null); setNewEnvName(''); setNewEnvBaseUrl(''); setNewEnvVars([{ key: '', value: '' }]); }}>取消</button>
                <button className="create-btn" onClick={saveEditEnv}>保存</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showFolderModal && (
        <div className="modal-overlay" onClick={() => setShowFolderModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{newFolderParentId ? '创建子文件夹' : '创建文件夹'}</h2>
            <input type="text" placeholder="文件夹名称" value={newFolderName} onChange={e => setNewFolderName(e.target.value)} className="modal-input" autoFocus onKeyDown={e => { if (e.key === 'Enter') createFolder(); }} />
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowFolderModal(false)}>取消</button>
              <button className="create-btn" onClick={createFolder}>创建</button>
            </div>
          </div>
        </div>
      )}

      {showRenameModal && (
        <div className="modal-overlay" onClick={() => setShowRenameModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>重命名{showRenameModal.type === 'folder' ? '文件夹' : '请求'}</h2>
            <input type="text" value={renameValue} onChange={e => setRenameValue(e.target.value)} className="modal-input" autoFocus onKeyDown={e => { if (e.key === 'Enter') renameItem(); }} />
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowRenameModal(null)}>取消</button>
              <button className="create-btn" onClick={renameItem}>确定</button>
            </div>
          </div>
        </div>
      )}

      {confirmModal && (
        <div className="modal-overlay" onClick={() => setConfirmModal(null)}>
          <div className="modal confirm-modal" onClick={e => e.stopPropagation()}>
            <p className="confirm-message">{confirmModal.message}</p>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setConfirmModal(null)}>取消</button>
              <button className="create-btn danger-btn" onClick={confirmModal.onConfirm}>确定</button>
            </div>
          </div>
        </div>
      )}

      {showSavePanel && (
        <div className="modal-overlay" onClick={() => setShowSavePanel(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>保存接口</h2>
            <input type="text" placeholder="请输入接口名称" value={saveName} onChange={e => setSaveName(e.target.value)} className="modal-input" autoFocus onKeyDown={e => { if (e.key === 'Enter') handleSaveConfirm(); }} />
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowSavePanel(false)}>取消</button>
              <button className="create-btn" onClick={handleSaveConfirm} disabled={!saveName.trim()}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
