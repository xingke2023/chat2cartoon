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

import { forwardRef, useImperativeHandle, useState } from 'react';

import { useTransition, animated } from '@react-spring/web';

import s from './index.module.less';

const STEPS = ['生成故事创意', '生成分镜脚本', '生成故事视频'];

export const StepsSection = ({ visible }: { visible: boolean }) => {
  const transitions = useTransition(visible, {
    from: { opacity: 0, transform: 'translateX(100%)' },
    enter: { opacity: 1, transform: 'translateX(0%)' },
    leave: { opacity: 0, transform: 'translateX(100%)' },
  });

  return transitions(
    (styles, item) =>
      item && (
        <animated.div style={styles}>
          <div className={s.stepsBar}>
            {STEPS.map((label, i) => (
              <div key={i} className={s.stepItem}>
                <span className={s.stepIndex}>{i + 1}</span>
                <span className={s.stepLabel}>{label}</span>
                {i < STEPS.length - 1 && <span className={s.stepDivider} />}
              </div>
            ))}
          </div>
        </animated.div>
      ),
  );
};

export const FlowMiniMap = forwardRef<{
  close: () => void;
}>((_, ref) => {
  const [visible, setVisible] = useState(true);

  useImperativeHandle(ref, () => ({
    close: () => {
      setVisible(false);
    },
  }));

  return (
    <div className={'relative'}>
      <StepsSection visible={visible} />
    </div>
  );
});
