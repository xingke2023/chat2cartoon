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

import { useEffect, useState, useMemo } from 'react';
import { Helmet } from '@modern-js/runtime/head';
import { v4 as uuidV4 } from 'uuid';
import { useSpring, animated, config } from '@react-spring/web';
import VideoGenerator from '@/module/VideoGenerator';
import doubaoLogo from '@/images/assets/doubao_logo.png';

import './index.css';
import { GetVideoGenTask } from '@/services/getVideoGenTask';
import { 
  MODE_CHILDREN_STORY, 
  MODE_INSURANCE_CASE, 
  MODE_STORY_NARRATION, 
  MODE_TEXT_TO_STORYBOARD, 
  MODE_CONFIG, 
  DEFAULT_EXTRA_INFO 
} from '@/module/VideoGenerator/constants';

const ACCESS_PASSWORD = process.env.ACCESS_PASSWORD || '';

const Card = ({ mode, config: modeConfig, onSelect, colorIndex }: { 
  mode: string, 
  config: any, 
  onSelect: (mode: string) => void,
  colorIndex: number
}) => {
  const [hovered, setHovered] = useState(false);
  
  const springProps = useSpring({
    transform: hovered ? 'translateY(-12px)' : 'translateY(0px)',
    boxShadow: hovered 
      ? '0 20px 40px rgba(0,0,0,0.3)' 
      : '0 8px 16px rgba(0,0,0,0.1)',
    background: hovered 
      ? 'rgba(255, 255, 255, 0.12)' 
      : 'rgba(255, 255, 255, 0.05)',
    border: hovered
      ? '1px solid rgba(255, 255, 255, 0.3)'
      : '1px solid rgba(255, 255, 255, 0.1)',
    config: config.gentle,
  });

  const iconGradients = [
    'linear-gradient(135deg, #6366f1, #a855f7)',
    'linear-gradient(135deg, #f43f5e, #fb923c)',
    'linear-gradient(135deg, #10b981, #3b82f6)',
    'linear-gradient(135deg, #f59e0b, #ef4444)',
  ];

  const icons = {
    [MODE_CHILDREN_STORY]: '🧸',
    [MODE_INSURANCE_CASE]: '🛡️',
    [MODE_STORY_NARRATION]: '🇭🇰',
    [MODE_TEXT_TO_STORYBOARD]: '📄',
  };

  return (
    <animated.div
      style={{
        ...springProps,
        width: 300,
        height: 380,
        borderRadius: 24,
        padding: '40px 32px',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'space-between',
        backdropFilter: 'blur(12px)',
        position: 'relative',
        overflow: 'hidden',
        boxSizing: 'border-box',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onSelect(mode)}
    >
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: 20,
          background: iconGradients[colorIndex % iconGradients.length],
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 40,
          marginBottom: 24,
          boxShadow: '0 8px 20px rgba(0,0,0,0.2)',
        }}
      >
        {icons[mode as keyof typeof icons] || '✨'}
      </div>
      
      <div style={{ textAlign: 'center', flex: 1 }}>
        <h3 style={{ 
          fontSize: 24, 
          fontWeight: 700, 
          color: '#fff', 
          marginBottom: 12,
          letterSpacing: '0.02em'
        }}>
          {modeConfig.name}
        </h3>
        <p style={{ 
          fontSize: 15, 
          color: 'rgba(255,255,255,0.7)', 
          lineHeight: 1.6,
          fontWeight: 400
        }}>
          {modeConfig.description}
        </p>
      </div>

      <div style={{
        marginTop: 'auto',
        width: '100%',
        padding: '12px 0',
        borderRadius: 14,
        background: hovered ? '#fff' : 'rgba(255,255,255,0.1)',
        color: hovered ? '#1e293b' : '#fff',
        fontSize: 16,
        fontWeight: 600,
        textAlign: 'center',
        transition: 'all 0.3s ease',
        border: '1px solid rgba(255,255,255,0.2)',
      }}>
        立即开始
      </div>
    </animated.div>
  );
};

const Background = () => {
  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      zIndex: -1,
      background: '#0f172a',
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute',
        top: '-10%',
        right: '-10%',
        width: '60%',
        height: '60%',
        background: 'radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%)',
        borderRadius: '50%',
      }} />
      <div style={{
        position: 'absolute',
        bottom: '-10%',
        left: '-10%',
        width: '60%',
        height: '60%',
        background: 'radial-gradient(circle, rgba(168, 85, 247, 0.1) 0%, transparent 70%)',
        borderRadius: '50%',
      }} />
    </div>
  );
};

const Index = () => {
  const [authed, setAuthed] = useState<boolean>(!ACCESS_PASSWORD);
  const [inputPwd, setInputPwd] = useState('');
  const [pwdError, setPwdError] = useState(false);
  const [selectedMode, setSelectedMode] = useState<string | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [pendingMode, setPendingMode] = useState<string | null>(null);
  const storeKey = useMemo(() => localStorage.getItem('ark-interactive-video-store-key') || uuidV4(), []);

  useEffect(() => {
    localStorage.setItem('ark-interactive-video-store-key', storeKey);
  }, [storeKey]);

  const handleSelectMode = (mode: string) => {
    if (authed) {
      setSelectedMode(mode);
    } else {
      setPendingMode(mode);
      setShowAuthModal(true);
    }
  };

  const handleBack = () => {
    setSelectedMode(null);
  };

  const handleLogin = () => {
    if (inputPwd === ACCESS_PASSWORD) {
      setAuthed(true);
      setPwdError(false);
      setShowAuthModal(false);
      setSelectedMode(pendingMode);
      setPendingMode(null);
    } else {
      setPwdError(true);
    }
  };

  if (selectedMode) {
    const config = MODE_CONFIG[selectedMode as keyof typeof MODE_CONFIG];
    return (
      <div>
        <Helmet>
          <title>{config.name} - 港险宣传视频生成器</title>
          <link
            rel="icon"
            type="image/x-icon"
            href="https://lf3-static.bytednsdoc.com/obj/eden-cn/uhbfnupenuhf/favicon.ico"
          />
        </Helmet>
        <main>
          <div className="interactive-video" style={{ height: '100vh', background: '#f8fafc' }}>
            <div
              style={{
                position: 'absolute',
                top: 16,
                left: 16,
                zIndex: 100,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
            >
              <button
                onClick={handleBack}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 16px',
                  background: 'rgba(255,255,255,0.9)',
                  border: '1px solid #e2e8f0',
                  borderRadius: 12,
                  cursor: 'pointer',
                  fontSize: 14,
                  fontWeight: 500,
                  color: '#475569',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = '#fff')}
                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.9)')}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
                返回首页
              </button>
              <div style={{ height: 24, width: 1, background: '#e2e8f0' }} />
              <img src={doubaoLogo} alt="Doubao Logo" style={{ height: 28, opacity: 0.8 }} />
            </div>
            <VideoGenerator
              assistantInfo={{
                Name: config.assistantName,
                Description: config.description,
                OpeningRemarks: {
                  OpeningRemark: config.openingRemark,
                  OpeningQuestions: config.openingQuestions,
                },
                Extra: {
                  Mode: selectedMode,
                  Models: DEFAULT_EXTRA_INFO.Models,
                  Tones: DEFAULT_EXTRA_INFO.Tones,
                },
              }}
              botUrl="/api/v3/bots/chat/completions"
              botChatUrl="/api/v3/bots/chat/completions"
              storeUniqueId={storeKey}
              api={{
                GetVideoGenTask: GetVideoGenTask,
              }}
              slots={{}}
            />
          </div>
        </main>
      </div>
    );
  }

  const modes = [
    { key: MODE_STORY_NARRATION, config: MODE_CONFIG[MODE_STORY_NARRATION] },
    { key: MODE_TEXT_TO_STORYBOARD, config: MODE_CONFIG[MODE_TEXT_TO_STORYBOARD] },
  ];

  return (
    <div>
      <Helmet>
        <title>港险宣传视频生成器</title>
        <link
          rel="icon"
          type="image/x-icon"
          href="https://lf3-static.bytednsdoc.com/obj/eden-cn/uhbfnupenuhf/favicon.ico"
        />
      </Helmet>
      <main>
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 24px',
          boxSizing: 'border-box',
          position: 'relative',
        }}>
          <Background />
          
          <div style={{
            position: 'absolute',
            top: 24,
            left: 32,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}>
            <img src={doubaoLogo} alt="Doubao Logo" style={{ height: 32 }} />
            <div style={{ fontSize: 18, fontWeight: 600, color: '#fff', opacity: 0.9 }}>
              保险人文案转视频制作工具
            </div>
          </div>

          <div style={{ textAlign: 'center', marginBottom: 64 }}>
            <h1 style={{
              color: '#fff',
              fontSize: 'min(56px, 10vw)',
              fontWeight: 800,
              marginBottom: 20,
              letterSpacing: '-0.03em',
              background: 'linear-gradient(135deg, #fff 30%, rgba(255,255,255,0.7) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>
              港险宣传视频生成器
            </h1>
            <p style={{
              color: 'rgba(255,255,255,0.6)',
              fontSize: 20,
              fontWeight: 400,
              maxWidth: 800,
              margin: '0 auto',
              lineHeight: 1.6,
            }}>
              通过自然对话将您的文字灵感转化为生动的配音动画分镜。
            </p>
          </div>

          <div style={{
            display: 'flex',
            gap: 16,
            width: '100%',
            maxWidth: 800,
            justifyContent: 'center',
          }}>
            {modes.map((item, index) => (
              <Card 
                key={item.key} 
                mode={item.key} 
                config={item.config} 
                onSelect={handleSelectMode} 
                colorIndex={index}
              />
            ))}
          </div>

          {/* 案例视频展示 */}
          <div style={{
            display: 'flex',
            gap: 24,
            width: '100%',
            maxWidth: 1100,
            justifyContent: 'center',
            flexWrap: 'wrap',
            marginTop: 48,
          }}>
            {['/videos/Film_storybook8.mp4', '/videos/Film_storybook9.mp4'].map((src, i) => (
              <div key={i} style={{
                flex: '1 1 280px',
                maxWidth: 360,
                borderRadius: 16,
                overflow: 'hidden',
                border: '1px solid rgba(255,255,255,0.1)',
                boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                background: 'rgba(0,0,0,0.3)',
              }}>
                <video src={src} controls style={{ width: '100%', display: 'block' }} />
                <div style={{ padding: '10px 14px', fontSize: 13, color: 'rgba(255,255,255,0.6)', fontWeight: 500 }}>
                  案例 {i + 1}
                </div>
              </div>
            ))}
          </div>

          <div style={{
            marginTop: 48,
            padding: '20px 32px',
            background: 'rgba(255,255,255,0.03)',
            borderRadius: 20,
            border: '1px solid rgba(255,255,255,0.05)',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
          }}>
            <div style={{ width: 8, height: 8, background: '#10b981', borderRadius: '50%', boxShadow: '0 0 12px #10b981' }} />
            <span style={{ fontSize: 14, color: 'rgba(255,255,255,0.4)', fontWeight: 500 }}>
              AI 生成能力已就绪 · 全程支持双语内容生成
            </span>
          </div>
        </div>
      </main>

      {/* 身份验证模态框 */}
      {showAuthModal && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(8px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={e => { if (e.target === e.currentTarget) { setShowAuthModal(false); setInputPwd(''); setPwdError(false); } }}
        >
          <div style={{
            background: 'rgba(15,23,42,0.95)',
            backdropFilter: 'blur(16px)',
            borderRadius: 24,
            padding: '48px 40px',
            width: '100%',
            maxWidth: 400,
            boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
            border: '1px solid rgba(255,255,255,0.1)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 24,
          }}>
            <div style={{ width: 80, height: 80, background: 'rgba(255,255,255,0.1)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 }}>🔒</div>
            <div style={{ textAlign: 'center' }}>
              <h2 style={{ fontSize: 24, fontWeight: 700, color: '#fff', marginBottom: 8 }}>身份验证</h2>
              <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.5)' }}>请输入访问密码以继续</p>
            </div>
            <input
              type="password"
              value={inputPwd}
              onChange={e => { setInputPwd(e.target.value); setPwdError(false); }}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              autoFocus
              placeholder="访问密码"
              style={{
                width: '100%', padding: '14px 18px',
                background: 'rgba(0,0,0,0.2)',
                border: `1px solid ${pwdError ? '#ef4444' : 'rgba(255,255,255,0.1)'}`,
                borderRadius: 12, fontSize: 16, color: '#fff',
                outline: 'none', boxSizing: 'border-box', transition: 'all 0.3s ease',
              }}
            />
            {pwdError && <div style={{ color: '#ef4444', fontSize: 13, marginTop: -8 }}>密码错误，请重试</div>}
            <button
              onClick={handleLogin}
              style={{
                width: '100%', padding: '14px 0',
                background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                color: '#fff', border: 'none', borderRadius: 12,
                fontSize: 16, fontWeight: 600, cursor: 'pointer', transition: 'transform 0.2s ease',
              }}
              onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.02)')}
              onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
            >
              立即进入
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Index;
