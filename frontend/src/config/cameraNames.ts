// 摄像头名称配置
// 根据 sourceId 映射到对应的摄像头名称
export const CAMERA_NAMES: Record<number, string> = {
  0: '大厅主视角',
  1: '走廊南侧',
  2: '停车场入口',
  3: '服务器机房',
  4: '大门外侧',
  5: '货运码头',
  6: '员工餐厅',
  7: '周边公路',
  8: '前台服务区',
};

// 获取摄像头名称
export function getCameraName(sourceId: number): string {
  return CAMERA_NAMES[sourceId] || `摄像头 ${sourceId + 1}`;
}

