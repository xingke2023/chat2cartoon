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

import { useContext, useMemo } from 'react';
import clsx from 'classnames';

import { Button } from '@arco-design/web-react';

import { IconClean } from '@/images/iconBox';
import { ChatWindowContext } from '@/components/ChatWindowV2/context';
import { WatchAndChat } from '@/module/WatchAndChat';
import { useStartChatWithVideo } from '@/module/WatchAndChat/providers/WatchAndChatProvider/hooks/useStartChatWithVideo';

import { RenderedMessagesContext } from '../../store/RenderedMessages/context';
import styles from './index.module.less';
import ChatArea from '../ChatArea';
import { VideoGeneratorMessageType, VideoGeneratorTaskPhase } from '../../types';
import { FlowMiniMap } from '../FlowMiniMap';
import { usePlaceholderInfo } from './hooks/usePlaceholderInfo';
import { useScrollToBottom } from '../../hooks/useScrollToBottom';
import { Placeholder } from './components/Placeholder';
import { MessageInput } from './components/MessageInput';
import { InjectContext } from '../../store/Inject/context';


const Conversation = () => {
  const { slots } = useContext(InjectContext);
  const { LimitIndicator } = slots;
  const { messages, sending, assistantInfo, sendMessageFromInput, startReply, insertBotEmptyMessage } =
    useContext(ChatWindowContext);
  const { miniMapRef, renderedMessages, finishPhase, autoNext, resetMessages } =
    useContext(RenderedMessagesContext);

  const placeholderInfoShow = usePlaceholderInfo({ assistant: assistantInfo });

  const showMessageList = useMemo(() => messages.length > 0, [messages]);

  const { scrollRef: chatMessageListRef, setAutoScroll } = useScrollToBottom(!autoNext);

  const handleScroll = (e: HTMLElement) => {
    if (autoNext) {
      return;
    }
    const bottomHeight = e.scrollTop + e.clientHeight;
    const isHitBottom = e.scrollHeight - bottomHeight <= 150;

    setAutoScroll(isHitBottom);
  };

  const handleSend = (value = '') => {
    if (!value || sending) {
      return;
    }
    miniMapRef.current?.close();
    // 用户消息加入到列表
    sendMessageFromInput(value);

    // 插入 bot 占位
    setTimeout(() => {
      insertBotEmptyMessage();
      // 请求接口
      startReply();
    }, 10);
  };

  const getPlaceHolderProps = () => ({
    chatStarted: showMessageList,
    onQuestionClick: handleSend,
    ...placeholderInfoShow,
  });

  const { visible: isFullScreen } = useStartChatWithVideo();

  return (
    <div className={clsx(styles.conversationWrapper, "bg-[#F8FAFC]")}>
      <div className={styles.displayBar}>
      </div>
      <div className={styles.conversationContainer}>
        <div
          className={clsx(styles.conversationChatAreaContainer, "pb-40")}
          ref={chatMessageListRef}
          onScroll={e => handleScroll(e.currentTarget)}
        >
          <div className="max-w-4xl mx-auto w-full px-4 md:px-8">
            <Placeholder {...(getPlaceHolderProps() as any)} />
            <ChatArea messages={renderedMessages} />
          </div>
        </div>
        {!isFullScreen && !renderedMessages.find(item => item.type === VideoGeneratorMessageType.Multiple) && (
          <div className={clsx(
            styles.conversationInputContainer,
            "absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#F8FAFC] via-[#F8FAFC]/90 to-transparent pt-12 pb-8 px-4"
          )}>
            <div className="max-w-3xl mx-auto w-full">
              {(!finishPhase ||
                [VideoGeneratorTaskPhase.PhaseScript, VideoGeneratorTaskPhase.PhaseStoryBoard].includes(
                  finishPhase as VideoGeneratorTaskPhase,
                )) && showMessageList && (
                <div className={styles.resetBtnWrapper}>
                  <Button
                    className={clsx(styles.resetBtn, "!rounded-full !bg-white !shadow-sm !border-[#E2E8F0] !text-slate-500 !text-xs !px-4 hover:!border-blue-500 transition-all")}
                    size="small"
                    icon={<IconClean />}
                    onClick={() => resetMessages()}
                  >
                    {'重置会话'}
                  </Button>
                </div>
              )}
              {!showMessageList && (
                <div className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-500" />
                  <MessageInput
                    activeSendBtn={true}
                    autoFocus
                    placeholder={'粘贴您的文案原文，我将为您自动拆解分镜...'}
                    canSendMessage={!sending}
                    sendMessage={handleSend}
                    extra={inputValue => LimitIndicator && <LimitIndicator text={inputValue} />}
                  />
                </div>
              )}
            </div>
          </div>
        )}
        <WatchAndChat />
      </div>
    </div>
  );
};

export default Conversation;
