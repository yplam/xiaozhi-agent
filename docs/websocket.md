# WebSocket 通信协议文档

本文档描述了客户端（设备）与服务器之间如何通过 WebSocket 进行通信交互。

## 1. 基本信息

- **协议版本**: 1
- **传输方式**: WebSocket
- **音频格式**: Opus
- **音频参数**:
  - 采样率: 16000Hz
  - 通道数: 1
  - 帧长: 60ms

## 2. 总体流程概览

1. **设备端初始化**
   - 设备上电、初始化应用
   - 连接网络
   - 创建并初始化 WebSocket 协议实例

2. **建立 WebSocket 连接**
   - 设备配置 WebSocket URL (`CONFIG_WEBSOCKET_URL`)
   - 设置请求头
   - 调用 `Connect()` 与服务器建立连接

3. **握手交换**
   - 客户端发送 "hello" 消息
   - 服务器回复 "hello" 消息
   - 握手成功后标记通道打开

4. **消息交互**
   - 二进制音频数据 (Opus 编码)
   - 文本 JSON 消息 (状态、事件、命令等)

5. **关闭 WebSocket 连接**
   - 主动调用 `CloseAudioChannel()` 断开连接
   - 或服务器主动断开

## 3. 连接建立

### 3.1 请求头

客户端连接 WebSocket 服务器时需要携带以下 headers:

```
Authorization: Bearer <access_token>
Protocol-Version: 1
Device-Id: <设备MAC地址>
Client-Id: <设备UUID>
```

### 3.2 握手交换

1. **客户端发送 hello 消息**:

```json
{
  "type": "hello",
  "version": 1,
  "transport": "websocket",
  "audio_params": {
    "format": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 60
  }
}
```

2. **服务端响应 hello 消息**:

```json
{
  "type": "hello",
  "transport": "websocket",
  "audio_params": {
    "sample_rate": 16000
  }
}
```

> 注：WebSocket 协议中 session_id 可设置为空，服务端不在握手中返回会话 ID。

## 4. JSON 消息结构

WebSocket 文本帧以 JSON 方式传输，以下是各类消息的结构。

### 4.1 客户端 → 服务器

#### 4.1.1 开始监听

```json
{
  "session_id": "<会话ID>",
  "type": "listen",
  "state": "start",
  "mode": "<监听模式>"
}
```

监听模式:

- `"auto"`: 自动停止
- `"manual"`: 手动停止
- `"realtime"`: 持续监听

#### 4.1.2 停止监听

```json
{
  "session_id": "<会话ID>",
  "type": "listen",
  "state": "stop"
}
```

#### 4.1.3 唤醒词检测

```json
{
  "session_id": "<会话ID>",
  "type": "listen",
  "state": "detect",
  "text": "<唤醒词>"
}
```

#### 4.1.4 中止会话

```json
{
  "session_id": "<会话ID>",
  "type": "abort",
  "reason": "wake_word_detected"  // 可选
}
```

#### 4.1.5 IoT 设备相关

设备描述:

```json
{
  "session_id": "<会话ID>",
  "type": "iot",
  "descriptors": <设备描述JSON>
}
```

设备状态:

```json
{
  "session_id": "<会话ID>",
  "type": "iot",
  "states": <状态JSON>
}
```

### 4.2 服务器 → 客户端

#### 4.2.1 语音识别结果 (STT)

```json
{
  "type": "stt",
  "text": "用户说的话"
}
```

#### 4.2.2 语音合成相关 (TTS)

```json
{
  "type": "tts",
  "state": "<状态>",
  "text": "<文本内容>"  // 仅在 sentence_start 时携带
}
```

状态类型:

- `"start"`: 开始播放
- `"stop"`: 停止播放
- `"sentence_start"`: 新句子开始（包含要朗读的文本）

#### 4.2.3 情感状态

```json
{
  "type": "llm",
  "emotion": "<情感类型>",
  "text": "😀"  // 可选，表情符号
}
```

#### 4.2.4 IoT 命令

```json
{
  "type": "iot",
  "commands": [ ... ]
}
```

## 5. 音频编解码

1. **客户端发送录音数据**
   - 音频输入经过可能的回声消除、降噪或音量增益后
   - 通过 Opus 编码打包为二进制帧
   - 通过 WebSocket 的 binary 消息发送

2. **客户端播放收到的音频**
   - 收到服务器的二进制帧时，视为 Opus 数据
   - 进行解码，然后交由音频输出接口播放
   - 如采样率不一致，在解码后进行重采样

## 6. 状态流转

设备端关键状态流转与 WebSocket 消息对应:

1. **空闲 (Idle) → 连接中 (Connecting)**
   - 用户触发或唤醒后
   - 设备调用 `OpenAudioChannel()`
   - 建立 WebSocket 连接
   - 发送 `"type":"hello"`

2. **连接中 (Connecting) → 监听中 (Listening)**
   - 成功建立连接后
   - 执行 `SendStartListening(...)`
   - 进入录音状态
   - 持续编码麦克风数据并发送到服务器

3. **监听中 (Listening) → 播放中 (Speaking)**
   - 收到服务器 TTS Start 消息 (`{"type":"tts","state":"start"}`)
   - 停止录音
   - 播放接收到的音频

4. **播放中 (Speaking) → 空闲 (Idle)**
   - 服务器 TTS Stop (`{"type":"tts","state":"stop"}`)
   - 音频播放结束
   - 若未继续进入自动监听，则返回空闲状态
   - 如配置了自动循环，则再度进入监听状态

5. **异常或中断 → 空闲 (Idle)**
   - 调用 `SendAbortSpeaking(...)` 或 `CloseAudioChannel()`
   - 中断会话
   - 关闭 WebSocket
   - 状态回到空闲

## 7. 错误处理

1. **连接失败**
   - 如果 `Connect(url)` 返回失败
   - 或在等待服务器 "hello" 消息时超时
   - 触发 `on_network_error_()` 回调
   - 设备提示"无法连接到服务"或类似错误信息

2. **服务器断开**
   - WebSocket 异常断开，回调 `OnDisconnected()`
   - 设备回调 `on_audio_channel_closed_()`
   - 切换到空闲状态或执行重试逻辑

## 8. 完整消息交互示例

下面给出一个典型的双向消息流程:

1. **客户端 → 服务器** (握手)

```json
{
  "type": "hello",
  "version": 1,
  "transport": "websocket",
  "audio_params": {
    "format": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 60
  }
}
```

2. **服务器 → 客户端** (握手应答)

```json
{
  "type": "hello",
  "transport": "websocket",
  "audio_params": {
    "sample_rate": 16000
  }
}
```

3. **客户端 → 服务器** (开始监听)

```json
{
  "session_id": "",
  "type": "listen",
  "state": "start",
  "mode": "auto"
}
```

*同时客户端开始发送二进制帧 (Opus 音频数据)*

4. **服务器 → 客户端** (语音识别结果)

```json
{
  "type": "stt",
  "text": "用户说的话"
}
```

5. **服务器 → 客户端** (开始语音合成)

```json
{
  "type": "tts",
  "state": "start"
}
```

*接着服务器发送二进制音频帧给客户端播放*

6. **服务器 → 客户端** (语音合成结束)

```json
{
  "type": "tts",
  "state": "stop"
}
```

*客户端停止播放音频，若无更多指令，则回到空闲状态*

## 9. 其它注意事项

1. **鉴权**
   - 设备通过设置 `Authorization: Bearer <token>` 提供鉴权
   - 服务器端需验证是否有效
   - 如令牌过期或无效，服务器可拒绝握手或在后续断开

2. **会话控制**
   - 消息中包含 `session_id`，用于区分独立的对话或操作
   - 服务端可根据需要对不同会话做分离处理

3. **音频负载**
   - 使用 Opus 格式，采样率 16000Hz，单声道
   - 帧时长由 `OPUS_FRAME_DURATION_MS` 控制，一般为 60ms
   - 可根据带宽或性能做适当调整

4. **IoT 指令**
   - `"type":"iot"` 的消息用于控制或获取设备状态
   - 服务器端需确保下发格式与客户端保持一致

5. **错误或异常 JSON**
   - 当 JSON 中缺少必要字段，例如 `{"type": ...}`
   - 客户端会记录错误日志，不执行任何业务

## 10. 总结

本协议通过 WebSocket 传输 JSON 文本与二进制音频帧，完成以下功能:

- 音频流上传 (设备麦克风输入)
- 语音识别结果下发 (STT)
- TTS 音频播放 (服务器生成的语音)
- IoT 指令下发与状态上报
- 情感与界面状态控制

其核心特征:

- **握手阶段**: 发送 `"type":"hello"`，等待服务器返回
- **音频通道**: 采用 Opus 编码的二进制帧双向传输语音流
- **JSON 消息**: 使用 `"type"` 为核心字段标识不同业务逻辑
- **扩展性**: 可根据实际需求在 JSON 消息中添加字段，或在 headers 里进行额外鉴权

服务器与客户端需提前约定各类消息的字段含义、时序逻辑以及错误处理规则，以保证通信顺畅。
