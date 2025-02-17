import { FC, ReactNode } from 'react';
import { PanelSectionRow, DialogButton, Field, Focusable } from 'decky-frontend-lib';

export interface ButtonConfig {
    content: ReactNode;
    onClick: (e: MouseEvent) => void;
    disabled: boolean;
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
                <div>
                    {icon && (<div style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '.5em' }}>{icon}</div>)}
                    {label && (<span style={{ fontSize: '1em' }}>{label}</span>)}
                </div>
                <div style={{ display: 'flex' }}>
                    <DialogButton onClick={primaryButtonConfig.onClick}
                        disabled={primaryButtonConfig.disabled}
                        style={{ padding: '10px', fontSize: '14px' }}
                    >
                        {primaryButtonConfig.content}
                    </DialogButton>
                    {secondaryButtonConfig && (
                        <DialogButton
                            onClick={secondaryButtonConfig.onClick}
                            disabled={secondaryButtonConfig.disabled}
                            style={{ padding: '10px', maxWidth: '40px', minWidth: 'auto', marginLeft: '.5em' }}
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
