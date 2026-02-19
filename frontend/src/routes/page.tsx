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

import { useEffect, useState } from 'react';
import { Helmet } from '@modern-js/runtime/head';
import { v4 as uuidV4 } from 'uuid';
import VideoGenerator from '@/module/VideoGenerator';

import './index.css';
import { GetVideoGenTask } from '@/services/getVideoGenTask';
import { MODE_CHILDREN_STORY, MODE_INSURANCE_CASE, MODE_CONFIG } from '@/module/VideoGenerator/constants';

const Index = () => {
  const [selectedMode, setSelectedMode] = useState<string | null>(null);
  const storeKey =
    localStorage.getItem('ark-interactive-video-store-key') || uuidV4();

  useEffect(() => {
    localStorage.setItem('ark-interactive-video-store-key', storeKey);
  }, []);

  const handleSelectMode = (mode: string) => {
    setSelectedMode(mode);
  };

  const handleBack = () => {
    setSelectedMode(null);
  };

  if (selectedMode) {
    const config = MODE_CONFIG[selectedMode as keyof typeof MODE_CONFIG];
    return (
      <div>
        <Helmet>
          <link
            rel="icon"
            type="image/x-icon"
            href="https://lf3-static.bytednsdoc.com/obj/eden-cn/uhbfnupenuhf/favicon.ico"
          />
        </Helmet>
        <main>
          <div className="interactive-video" style={{ height: '100vh' }}>
            <div
              style={{
                position: 'absolute',
                top: 12,
                left: 12,
                zIndex: 100,
              }}
            >
              <button
                onClick={handleBack}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '6px 12px',
                  background: 'rgba(255,255,255,0.9)',
                  border: '1px solid #e0e0e0',
                  borderRadius: 8,
                  cursor: 'pointer',
                  fontSize: 13,
                  color: '#555',
                }}
              >
                ← 返回
              </button>
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

  return (
    <div>
      <Helmet>
        <link
          rel="icon"
          type="image/x-icon"
          href="https://lf3-static.bytednsdoc.com/obj/eden-cn/uhbfnupenuhf/favicon.ico"
        />
      </Helmet>
      <main>
        <div
          style={{
            minHeight: '100vh',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
        >
          <h1
            style={{
              color: '#fff',
              fontSize: 32,
              fontWeight: 700,
              marginBottom: 8,
              textAlign: 'center',
            }}
          >
            互动双语视频生成器
          </h1>
          <p
            style={{
              color: 'rgba(255,255,255,0.8)',
              fontSize: 16,
              marginBottom: 48,
              textAlign: 'center',
            }}
          >
            请选择内容模式
          </p>
          <div
            style={{
              display: 'flex',
              gap: 24,
              flexWrap: 'wrap',
              justifyContent: 'center',
            }}
          >
            {/* 儿童故事卡片 */}
            <div
              onClick={() => handleSelectMode(MODE_CHILDREN_STORY)}
              style={{
                width: 280,
                background: '#fff',
                borderRadius: 16,
                padding: '32px 24px',
                cursor: 'pointer',
                boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
                transition: 'transform 0.2s, box-shadow 0.2s',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 16,
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-4px)';
                (e.currentTarget as HTMLDivElement).style.boxShadow = '0 12px 40px rgba(0,0,0,0.18)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)';
                (e.currentTarget as HTMLDivElement).style.boxShadow = '0 8px 32px rgba(0,0,0,0.12)';
              }}
            >
              <div
                style={{
                  fontSize: 56,
                  lineHeight: 1,
                }}
              >
                🧸
              </div>
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: '#333',
                    marginBottom: 8,
                  }}
                >
                  儿童故事
                </div>
                <div
                  style={{
                    fontSize: 14,
                    color: '#888',
                    lineHeight: 1.6,
                  }}
                >
                  为3-6岁小朋友生成
                  <br />
                  睡前动画故事
                </div>
              </div>
              <div
                style={{
                  marginTop: 8,
                  padding: '10px 24px',
                  background: 'linear-gradient(135deg, #667eea, #764ba2)',
                  color: '#fff',
                  borderRadius: 24,
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                开始创作
              </div>
            </div>

            {/* 保险案例卡片 */}
            <div
              onClick={() => handleSelectMode(MODE_INSURANCE_CASE)}
              style={{
                width: 280,
                background: '#fff',
                borderRadius: 16,
                padding: '32px 24px',
                cursor: 'pointer',
                boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
                transition: 'transform 0.2s, box-shadow 0.2s',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 16,
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-4px)';
                (e.currentTarget as HTMLDivElement).style.boxShadow = '0 12px 40px rgba(0,0,0,0.18)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)';
                (e.currentTarget as HTMLDivElement).style.boxShadow = '0 8px 32px rgba(0,0,0,0.12)';
              }}
            >
              <div
                style={{
                  fontSize: 56,
                  lineHeight: 1,
                }}
              >
                🛡️
              </div>
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: '#333',
                    marginBottom: 8,
                  }}
                >
                  保险案例
                </div>
                <div
                  style={{
                    fontSize: 14,
                    color: '#888',
                    lineHeight: 1.6,
                  }}
                >
                  将真实保险案例转化为
                  <br />
                  生动的动画故事
                </div>
              </div>
              <div
                style={{
                  marginTop: 8,
                  padding: '10px 24px',
                  background: 'linear-gradient(135deg, #f093fb, #f5576c)',
                  color: '#fff',
                  borderRadius: 24,
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                开始创作
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;
