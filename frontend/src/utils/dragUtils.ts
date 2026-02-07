import type { DragItemType, DropTarget } from '../types';

/**
 * 计算缝隙位置：根据鼠标 Y 坐标和元素边界矩形，判断应插入到元素的上方还是下方。
 */
export function calcGapPosition(
  mouseY: number,
  elementRect: { top: number; height: number }
): 'before' | 'after' {
  const midY = elementRect.top + elementRect.height / 2;
  return mouseY < midY ? 'before' : 'after';
}

/**
 * 通用列表重排序函数：将拖拽项移动到参考项的指定位置（前方或后方）。
 */
export function reorderList<T extends { id: number }>(
  items: T[],
  dragId: number,
  refId: number,
  position: 'before' | 'after'
): T[] {
  const dragItem = items.find(item => item.id === dragId);
  if (!dragItem) return items;

  const remaining = items.filter(item => item.id !== dragId);
  const refIndex = remaining.findIndex(item => item.id === refId);
  if (refIndex === -1) return items;

  const insertIndex = position === 'before' ? refIndex : refIndex + 1;
  const result = [...remaining];
  result.splice(insertIndex, 0, dragItem);
  return result;
}

/**
 * 放置目标验证函数：根据拖拽项类型和放置目标，判断该放置操作是否合法。
 *
 * 规则：
 * - 请求 (request) 可放置到请求缝隙或文件夹上
 * - 文件夹 (folder) 可放置到文件夹缝隙或其他文件夹上
 */
export function isValidDrop(
  dragType: DragItemType,
  dropTarget: DropTarget
): boolean {
  if (dropTarget.type === 'gap') {
    switch (dragType) {
      case 'request':
        return dropTarget.refType === 'request';
      case 'folder':
        return dropTarget.refType === 'folder';
      default:
        return false;
    }
  } else if (dropTarget.type === 'folder') {
    switch (dragType) {
      case 'request':
        return true;
      case 'folder':
        return true;
      default:
        return false;
    }
  }

  return false;
}
