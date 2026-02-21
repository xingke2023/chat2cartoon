// Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
// Licensed under the 【火山方舟】原型应用软件自用许可协议
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//     https://www.volcengine.com/docs/82379/1433703
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { FC } from 'react';

import styles from './index.module.less';

const STEP_LABELS = ['生成视频文案脚本', '生成分镜脚本(角色|画面|台词)', '生成角色|分镜画面|视频剪辑'];

interface Props {
  id: number;
  content: string;
  stepIndex: number;
}

const UserMessage: FC<Props> = ({ stepIndex }) => {
  const label = STEP_LABELS[stepIndex] ?? `步骤 ${stepIndex + 1}`;
  return (
    <div className={styles.stepTitle}>
      <span className={styles.stepIndex}>{stepIndex + 1}</span>
      <span className={styles.stepLabel}>{label}</span>
    </div>
  );
};

export default UserMessage;
