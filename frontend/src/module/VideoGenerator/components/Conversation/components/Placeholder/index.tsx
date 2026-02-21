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

import { FC, Fragment, useEffect, useMemo, useState } from 'react';
import clsx from 'classnames';
import styles from './index.module.less';

interface Props {
  name: string;
  avatar: string;
  openingRemark:
    | string
    | {
        name: string;
        avatar: string;
        content: string;
      }[];
  preQuestions: string[];
  onQuestionClick: (question: string) => void;
  chatStarted: boolean;
  disabled: boolean;
}

const Avatar = ({ avatar }: { avatar: string }) => (
  <div className="relative">
    <div className="absolute inset-0 bg-blue-500/20 blur-2xl rounded-full scale-150" />
    <img 
      className="w-24 h-24 border-4 border-white/20 shadow-2xl rounded-full relative z-10 object-cover" 
      src={avatar} 
      alt="avatar" 
    />
  </div>
);

const Name = ({ name }: { name: string }) => (
  <div className="text-3xl font-extrabold tracking-tight text-slate-800 mb-2">
    {name}
  </div>
);

const OpeningRemark = ({
  openingRemark,
}: {
  openingRemark:
    | string
    | {
        name: string;
        avatar: string;
        content: string;
      }[];
}) => {
  const isArray = Array.isArray(openingRemark);

  if (!openingRemark) {
    return null;
  }
  return isArray ? (
    <div className="max-w-2xl w-full px-6">
      {openingRemark
        .filter(o => Boolean(o.content))
        .map(({ avatar, name, content }, idx) => (
          <div className={clsx(idx !== 0 && 'mt-6', "flex flex-col items-center")} key={name}>
            <div className="flex items-center gap-2 mb-2">
              <img src={avatar} className="rounded-full w-6 h-6 border border-white/50" />
              <div className="text-slate-500 text-xs font-semibold uppercase tracking-wider">{name}</div>
            </div>
            <div className="bg-white/80 backdrop-blur-md border border-white/50 shadow-sm px-6 py-4 rounded-2xl text-slate-700 text-center text-lg leading-relaxed italic">
              "{content}"
            </div>
          </div>
        ))}
    </div>
  ) : (
    <div className="max-w-xl text-slate-500 text-center text-lg leading-relaxed px-8 mb-8 font-light">
      {openingRemark}
    </div>
  );
};

const PreQuestions = ({
  preQuestions,
  onQuestionClick,
  disabled,
}: {
  preQuestions: string[];
  onQuestionClick: (question: string) => void;
  disabled?: boolean;
}) => {
  const questions = useMemo(
    () => preQuestions.filter(preQ => Boolean(preQ)),
    [preQuestions]
  );

  return (
    <div className="flex flex-col gap-3 w-full max-w-md px-6">
      <div className="text-xs font-bold text-slate-400 uppercase tracking-widest text-center mb-1">推荐场景</div>
      {questions.map((question) => (
        <button
          key={question}
          disabled={disabled}
          onClick={() => onQuestionClick(question)}
          className={clsx(
            "group relative px-6 py-4 bg-white hover:bg-slate-50 border border-slate-100 shadow-sm hover:shadow-md rounded-2xl transition-all duration-300 text-left flex items-center gap-4",
            disabled && "opacity-50 cursor-not-allowed"
          )}
        >
          <div className="w-8 h-8 rounded-full bg-slate-50 group-hover:bg-blue-50 flex items-center justify-center text-blue-500 transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </div>
          <span className="text-slate-700 text-[15px] font-medium leading-snug">{question}</span>
        </button>
      ))}
    </div>
  );
};

export const Placeholder: FC<Props> = ({
  disabled,
  chatStarted,
  avatar,
  name,
  openingRemark,
  preQuestions,
  onQuestionClick,
}) => {
  const [isAnimating, setIsAnimating] = useState(true);
  
  useEffect(() => {
    const timer = setTimeout(() => setIsAnimating(false), 300);
    return () => clearTimeout(timer);
  }, []);

  if (chatStarted) {
    return openingRemark ? (
       <div className="pt-8 pb-4 opacity-50 grayscale transition-all hover:opacity-100 hover:grayscale-0">
         <div className="flex flex-col items-center gap-2">
            <img src={avatar} className="w-10 h-10 rounded-full border-2 border-white shadow-sm" alt="" />
            <div className="text-xs font-bold text-slate-400">{name}</div>
         </div>
       </div>
    ) : null;
  }

  return (
    <div
      className={clsx(
        'w-full min-h-[70vh] flex flex-col items-center justify-center py-12 transition-all duration-700 ease-out',
        isAnimating ? 'translate-y-8 opacity-0' : 'translate-y-0 opacity-100'
      )}
    >
      <div className="flex flex-col items-center mb-8">
        <Avatar avatar={avatar} />
        <div className="mt-6 text-center">
          <Name name={name} />
          <div className="h-1 w-12 bg-blue-500/20 rounded-full mx-auto" />
        </div>
      </div>
      
      <OpeningRemark openingRemark={openingRemark} />
      
      <PreQuestions 
        disabled={disabled} 
        onQuestionClick={onQuestionClick} 
        preQuestions={preQuestions} 
      />
    </div>
  );
};

