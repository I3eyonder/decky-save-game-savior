import { CSSProperties, FC, ReactNode } from 'react';
import { PanelSectionRow, DialogButton, Field, Focusable } from 'decky-frontend-lib';

export interface ButtonConfig {
    content: ReactNode;
    onClick: (e: MouseEvent) => void;
    disabled?: boolean;
    extraStyle?: CSSProperties;
}

interface SnapshotButtonItemProps {
    icon?: ReactNode;
    label?: ReactNode;
    description?: ReactNode;
    primaryButtonConfig: ButtonConfig;
    secondaryButtonConfig?: ButtonConfig;
}

export const SnapshotButtonItem: FC<SnapshotButtonItemProps> = ({ icon, label, description, primaryButtonConfig, secondaryButtonConfig }) => (
    <PanelSectionRow>
        <Field
            bottomSeparator="none"
            icon={null}
            label={null}
            childrenLayout={undefined}
            inlineWrap="keep-inline"
            padding="none"
            spacingBetweenLabelAndChild="none"
            childrenContainerWidth="max"
        >
            <Focusable style={{ width: '100%', display: 'grid' }}>
                <div style={{ display: 'flex', gap: '.5em' }}>
                    {icon && (<div style={{ display: 'inline-block', verticalAlign: 'middle' }}>{icon}</div>)}
                    {label && (<span style={{ fontSize: '1em' }}>{label}</span>)}
                </div>
                <div style={{ display: 'flex', gap: '.5em' }}>
                    <DialogButton onClick={primaryButtonConfig.onClick}
                        disabled={primaryButtonConfig.disabled}
                        style={{ padding: '10px', fontSize: '14px', flexGrow: '1', minWidth: 'auto', ...primaryButtonConfig.extraStyle }}
                    >
                        {primaryButtonConfig.content}
                    </DialogButton>
                    {secondaryButtonConfig && (
                        <DialogButton
                            onClick={secondaryButtonConfig.onClick}
                            disabled={secondaryButtonConfig.disabled}
                            style={{ padding: '10px', fontSize: '14px', flexGrow: '1', minWidth: 'auto', ...secondaryButtonConfig.extraStyle }}
                        >
                            {secondaryButtonConfig.content}
                        </DialogButton>
                    )}
                </div>
                {description && (<div style={{ marginTop: '.2em', fontSize: '0.7em', width: '100%' }}>
                    {description}
                </div>)}
            </Focusable>
        </Field>
    </PanelSectionRow>
);


export default SnapshotButtonItem;
